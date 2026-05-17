"""
署名ロジック
- is_mock_mode(): python-pkcs11 がない場合はモックモード
- SigningSession: PKCS#11 カードまたはテスト証明書でPDFに署名するセッション
"""

from io import BytesIO
from pathlib import Path
from typing import List, Optional

BRIDGE_DIR        = Path(__file__).parent
TEST_P12_PATH     = BRIDGE_DIR / 'test_cert.p12'
TEST_P12_PASS     = b'hpki_bridge_test'

# HPKI（医師・看護師カード）
MEDIS_SIGN_CA_PATH  = BRIDGE_DIR / 'medis_sign_ca.cer'         # HPKI-01-MedisSignCA2-forNonRepudiation (2015-2035)
MEDIS_AUTH_CA_PATH  = BRIDGE_DIR / 'medis_auth_ca.cer'         # HPKI-01-MedisAuthCA2-forAuthentication (2017-2037)
MHLW_ROOT_CA_PATH   = BRIDGE_DIR / 'mhlw_hpki_root_ca_v2.cer'  # MHLW HPKI Root CA V2

# J-LIS（マイナンバーカード 署名用 — 世代別 self-signed root）
JPKI_SIGN_CA01_PATH = BRIDGE_DIR / 'jpki_sign_ca01.cer'  # 2015-2025
JPKI_SIGN_CA02_PATH = BRIDGE_DIR / 'jpki_sign_ca02.cer'  # 2019-2029
JPKI_SIGN_CA03_PATH = BRIDGE_DIR / 'jpki_sign_ca03.cer'  # 2023-2033


def is_mock_mode() -> bool:
    """python-pkcs11 がインストールされていない場合は True"""
    try:
        import pkcs11  # noqa: F401
        return False
    except ImportError:
        return True


# ─── テスト証明書 ──────────────────────────────────────────────────────────────

def _ensure_test_cert() -> None:
    """初回起動時にテスト用自己署名証明書を生成する。"""
    if TEST_P12_PATH.exists():
        return

    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,           'HPKI テスト署名者'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,     'テスト訪問看護ステーション'),
        x509.NameAttribute(NameOID.COUNTRY_NAME,          'JP'),
    ])
    now  = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        name=b'hpki-test', key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(TEST_P12_PASS),
    )
    TEST_P12_PATH.write_bytes(p12)
    print(f'[bridge] テスト証明書を生成しました: {TEST_P12_PATH.name}')


# ─── 署名セッション ────────────────────────────────────────────────────────────

class SigningSession:
    """
    PKCS#11カードまたはテスト証明書を使った署名セッション。
    フォルダ一括処理中はこのセッションを使い回し、PINは1回だけ入力する。
    """

    def __init__(
        self,
        pin:        str,
        pkcs11_lib: Optional[str] = None,
        slot_no:    int           = 0,
        key_label:  Optional[str] = None,
        cert_label: Optional[str] = None,
        tsa_url:    Optional[str] = None,
    ):
        self._mock        = is_mock_mode() or not pkcs11_lib
        self._tsa_url     = tsa_url
        self._ctx         = None
        self._chain_certs: List = []   # 中間CA証明書（LTV埋め込み用）
        # カード種別: 'hpki' or 'jpki'（LTV・CA証明書の選択に使用）
        self._card_type   = 'jpki' if pkcs11_lib and 'JPKIPKCS11Sign' in pkcs11_lib else 'hpki'

        if self._mock:
            self._init_mock()
        else:
            self._init_pkcs11(pkcs11_lib, pin, slot_no, key_label, cert_label)

        self._build_pdf_signer()

    # ── 初期化 ────────────────────────────────────────────────────────────────

    def _init_mock(self) -> None:
        from pyhanko.sign import signers
        _ensure_test_cert()
        self._signer = signers.SimpleSigner.load_pkcs12(
            pfx_file   = str(TEST_P12_PATH),
            passphrase = TEST_P12_PASS,
        )

    def _resolve_jpki_sign_cert(self, lib: str, pin: str, slot_no: int):
        """
        JPKI トークン上の証明書を列挙し、対応する秘密鍵が存在する証明書を返す。
        CA証明書にはトークン上に秘密鍵がないため、秘密鍵の label/ID で突き合わせる。
        戻り値: (label: str, cert_id: bytes)
        """
        import pkcs11 as p11
        from pkcs11 import Attribute, ObjectClass
        from asn1crypto import x509 as asn1x509

        lib_obj = p11.lib(lib)
        slots = lib_obj.get_slots(token_present=True)
        if not slots:
            raise RuntimeError('カードスロットが見つかりません')

        slot = slots[slot_no] if slot_no < len(slots) else slots[0]
        token = slot.get_token()

        with token.open(user_pin=pin) as session:
            # ── ① 秘密鍵の label / ID を収集 ────────────────────────────────
            key_labels: set = set()
            key_ids:    set = set()
            try:
                for key in session.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY}):
                    try:
                        kl = key[Attribute.LABEL] or ''
                        if kl:
                            key_labels.add(kl)
                    except Exception:
                        pass
                    try:
                        ki = bytes(key[Attribute.ID])
                        if ki:
                            key_ids.add(ki)
                    except Exception:
                        pass
                print(f'[bridge] JPKI秘密鍵: labels={key_labels} ids={[x.hex() for x in key_ids]}', flush=True)
                # サポートされているメカニズムをログ出力（デバッグ用）
                try:
                    mechs = slot.get_mechanisms()
                    mech_names = [str(m) for m in mechs]
                    print(f'[bridge] JPKIメカニズム: {mech_names[:30]}', flush=True)
                except Exception as me:
                    print(f'[bridge] メカニズム取得エラー: {me}', flush=True)
            except Exception as e:
                print(f'[bridge] JPKI秘密鍵列挙エラー（続行）: {e}', flush=True)

            # ── ② 証明書を列挙して秘密鍵に対応するものを選択 ──────────────────
            cert_objs = list(session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
            print(f'[bridge] JPKI証明書数: {len(cert_objs)}', flush=True)

            best_by_label = None   # 秘密鍵 label と一致
            best_by_id    = None   # 秘密鍵 ID と一致

            for cert_obj in cert_objs:
                try:
                    try:
                        label = cert_obj[Attribute.LABEL] or ''
                    except Exception:
                        label = ''
                    try:
                        cert_id = bytes(cert_obj[Attribute.ID])
                    except Exception:
                        cert_id = b''
                    try:
                        der = bytes(cert_obj[Attribute.VALUE])
                        cert = asn1x509.Certificate.load(der)
                        subj = cert.subject.human_friendly
                    except Exception:
                        subj = '（解析不可）'

                    match_label = bool(label and label in key_labels)
                    match_id    = bool(cert_id and cert_id in key_ids)
                    print(f'[bridge]   証明書: label={label!r} id={cert_id.hex() if cert_id else ""} '
                          f'match_label={match_label} match_id={match_id} subj={subj}', flush=True)

                    if match_label and best_by_label is None:
                        best_by_label = (label, cert_id)
                    if match_id and best_by_id is None:
                        best_by_id = (label, cert_id)
                except Exception as e:
                    print(f'[bridge]   証明書解析エラー: {e}', flush=True)

            # label 一致を優先、なければ ID 一致
            chosen = best_by_label or best_by_id
            if chosen:
                print(f'[bridge]   → 署名用証明書として選択: label={chosen[0]!r}', flush=True)
                return chosen

        raise RuntimeError('JPKI トークン上に秘密鍵に対応する証明書が見つかりませんでした')

    def _init_pkcs11(
        self, lib: str, pin: str, slot_no: int,
        key_label: Optional[str], cert_label: Optional[str],
    ) -> None:
        from pyhanko.sign.pkcs11 import PKCS11SigningContext
        from pyhanko.config.pkcs11 import PKCS11SignatureConfig
        from asn1crypto import x509 as asn1x509

        # JPKI: 証明書が複数（署名用＋CA）存在するため事前にエンドエンティティ証明書を特定する
        # cert_label は渡さない — pyhanko が同ラベルで秘密鍵も検索して失敗するため
        # cert_id のみ渡すことで証明書・秘密鍵ともに ID で一意検索させる
        resolved_cert_id: Optional[bytes] = None
        if self._card_type == 'jpki' and not cert_label:
            try:
                _cert_label_log, resolved_cert_id = self._resolve_jpki_sign_cert(lib, pin, slot_no)
                print(f'[bridge] JPKI署名証明書を自動検出: label={_cert_label_log!r} id={resolved_cert_id.hex() if resolved_cert_id else ""}', flush=True)
                cert_label = None  # cert_label は意図的に設定しない
            except Exception as e:
                print(f'[bridge] JPKI証明書自動検出エラー（続行）: {e}', flush=True)

        # カード種別に応じてCA証明書をCMS署名の certificates フィールドに埋め込む
        # Acrobat はこのフィールドを優先してチェーン構築に使用する
        other_certs = []
        if self._card_type == 'jpki':
            # J-LIS（マイナンバーカード）: 自己署名ルートCA を全世代埋め込む
            ca_list = [
                (JPKI_SIGN_CA03_PATH, 'J-LIS 署名用CA3 (2023-)'),
                (JPKI_SIGN_CA02_PATH, 'J-LIS 署名用CA2 (2019-)'),
                (JPKI_SIGN_CA01_PATH, 'J-LIS 署名用CA1 (2015-)'),
            ]
        else:
            # HPKI（医師・看護師カード）: 認証用を優先
            ca_list = [
                (MEDIS_AUTH_CA_PATH, '認証用中間CA'),
                (MEDIS_SIGN_CA_PATH, '署名用中間CA'),
                (MHLW_ROOT_CA_PATH,  'ルートCA'),
            ]
        for ca_path, ca_label in ca_list:
            if ca_path.exists():
                c = asn1x509.Certificate.load(ca_path.read_bytes())
                other_certs.append(c)
                print(f'[bridge] {ca_label}証明書をCMSに追加: {c.subject.human_friendly}', flush=True)

        # HPKI/JPKI ともに CKM_RSA_PKCS (raw_mechanism=True) を使用する
        # JPKI DLL が報告するメカニズム: [1=RSA_PKCS, 544, 592] — CKM_SHA256_RSA_PKCS(64) は非対応
        use_raw = True

        config = PKCS11SignatureConfig(
            module_path        = lib,
            slot_no            = slot_no,
            key_label          = key_label or None,
            cert_label         = cert_label or None,
            cert_id            = resolved_cert_id or None,
            raw_mechanism      = use_raw,
            other_certs_to_pull = [],     # カードから追加取得しない（重複防止）
            other_certs        = other_certs if other_certs else None,
        )
        self._ctx    = PKCS11SigningContext(config=config, user_pin=pin)
        self._signer = self._ctx.__enter__()
        self._chain_certs = self._collect_chain_certs()

    def _collect_chain_certs(self) -> List:
        """カードの cert_registry から CA 証明書のみ取得する（end-entity 証明書を除く）"""
        try:
            from asn1crypto import x509 as asn1x509
            signing_cert = self._signer.signing_cert
            ca_certs = []
            for c in self._signer.cert_registry:
                if c == signing_cert:
                    continue
                # CA 証明書かどうか BasicConstraints.ca=True で判定
                try:
                    raw = asn1x509.Certificate.load(bytes(c.dump()))
                    bc = raw['tbs_certificate']['extensions'].value.get('basic_constraints')
                    if bc and bc['ca'].native:
                        ca_certs.append(c)
                        print(f'[bridge]   カードCA: {c.subject.human_friendly}', flush=True)
                    else:
                        print(f'[bridge]   スキップ(end-entity): {c.subject.human_friendly}', flush=True)
                except Exception:
                    pass   # BasicConstraints なし＝end-entity として無視
            print(f'[bridge] カードCA証明書: {len(ca_certs)}枚', flush=True)
            return ca_certs
        except Exception as e:
            print(f'[bridge] CA証明書取得をスキップ: {e}', flush=True)
            return []

    def _build_pdf_signer(self) -> None:
        from pyhanko.sign import signers, timestamps
        from pyhanko.sign.fields import SigSeedSubFilter
        timestamper = (
            timestamps.HTTPTimeStamper(self._tsa_url) if self._tsa_url else None
        )
        self._pdf_signer = signers.PdfSigner(
            signers.PdfSignatureMetadata(
                field_name = 'Signature',
                reason     = '電子署名',
                subfilter  = SigSeedSubFilter.ADOBE_PKCS7_DETACHED,
            ),
            signer      = self._signer,
            timestamper = timestamper,
        )

    # ── 公開API ───────────────────────────────────────────────────────────────

    @staticmethod
    def _unique_sig_field_name(writer) -> str:
        """PDF内の既存署名フィールドと重複しない名前を返す"""
        try:
            from pyhanko.sign.fields import enumerate_sig_fields
            existing = {name for name, _, _ in enumerate_sig_fields(writer)}
            base = 'Signature'
            if base not in existing:
                return base
            i = 1
            while f'{base}{i}' in existing:
                i += 1
            new_name = f'{base}{i}'
            print(f'[bridge] フィールド名を変更: {base} → {new_name}', flush=True)
            return new_name
        except Exception:
            return 'Signature'

    def get_cert_info(self) -> dict:
        try:
            cert = self._signer.signing_cert
            subj = str(cert.subject.human_friendly)
            issr = str(cert.issuer.human_friendly)
            exp  = getattr(cert, 'not_valid_after_utc', None) or cert.not_valid_after
            # SHA1 フィンガープリントを計算してログ出力（どの証明書が使われているか確認用）
            import hashlib
            sha1 = hashlib.sha1(cert.dump()).hexdigest().upper()
            print(f'[bridge] 署名証明書 SHA1: {sha1}', flush=True)
            print(f'[bridge] 署名証明書 Subject: {subj}', flush=True)
            print(f'[bridge] 署名証明書 Issuer:  {issr}', flush=True)
            return {'subject': subj, 'issuer': issr, 'notAfter': str(exp), 'mock': self._mock, 'sha1': sha1, 'cardType': self._card_type}
        except Exception:
            return {'subject': '取得失敗', 'issuer': '-', 'notAfter': '-', 'mock': self._mock, 'cardType': self._card_type}

    def sign_pdf(self, pdf_bytes: bytes) -> bytes:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign.fields import SigFieldSpec
        writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))

        # 既存の署名フィールド名と重複しないフィールド名を決定
        field_name = self._unique_sig_field_name(writer)
        if field_name != 'Signature':
            from pyhanko.sign import signers
            from pyhanko.sign.fields import SigSeedSubFilter
            from pyhanko.sign import timestamps
            timestamper = (
                timestamps.HTTPTimeStamper(self._tsa_url) if self._tsa_url else None
            )
            pdf_signer = signers.PdfSigner(
                signers.PdfSignatureMetadata(
                    field_name = field_name,
                    reason     = '電子署名',
                    subfilter  = SigSeedSubFilter.ADOBE_PKCS7_DETACHED,
                ),
                signer      = self._signer,
                timestamper = timestamper,
            )
        else:
            pdf_signer = self._pdf_signer

        out = BytesIO()
        pdf_signer.sign_pdf(writer, output=out)
        out.seek(0)
        signed = out.read()

        # 署名後に中間CA証明書・CRL等をDSSへ埋め込む（Acrobat信頼検証に必要）
        try:
            signed = self._embed_ltv(signed)
            print('[bridge] LTV情報を埋め込みました', flush=True)
        except Exception as e:
            print(f'[bridge] LTV埋め込みをスキップしました: {e}', flush=True)

        return signed

    def _get_crl_urls(self) -> List[str]:
        """
        署名証明書の CRL 配布点URLを返す。
        証明書の拡張から動的に取得し、取れなければカード種別のデフォルトを返す。
        """
        try:
            from cryptography import x509 as cx509
            cert_der = bytes(self._signer.signing_cert.dump())
            cert = cx509.load_der_x509_certificate(cert_der)
            urls = []
            try:
                cdp = cert.extensions.get_extension_for_class(cx509.CRLDistributionPoints)
                for dp in cdp.value:
                    for gn in dp.full_name:
                        val = getattr(gn, 'value', '')
                        if isinstance(val, str) and val.startswith('http'):
                            urls.append(val)
            except cx509.ExtensionNotFound:
                pass
            if urls:
                print(f'[bridge] CRL URL（証明書から取得）: {urls}', flush=True)
                return urls
        except Exception as e:
            print(f'[bridge] CRL URL取得エラー: {e}', flush=True)

        # フォールバック: カード種別の既知URL
        if self._card_type == 'hpki':
            return [
                'http://cert.medis.or.jp/sign/crl-sign2.crl',
                'http://cert.medis.or.jp/auth/crl-auth2.crl',
            ]
        # JPKI ルートCA は CRL なし（自己署名）
        return []

    def _embed_ltv(self, signed_bytes: bytes) -> bytes:
        """
        中間CA証明書とCRLをPDFのDSSに直接書き込む。
        チェーン検証を経由せず DocumentSecurityStore.add_dss() で埋め込む。
        Acrobat は DSS の証明書をチェーン構築に使用する。
        """
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation.dss import DocumentSecurityStore
        from asn1crypto import x509 as asn1x509
        import urllib.request

        # カード種別に応じてCA証明書リストを作成
        certs = []
        if self._card_type == 'jpki':
            ca_paths = [JPKI_SIGN_CA03_PATH, JPKI_SIGN_CA02_PATH, JPKI_SIGN_CA01_PATH]
        else:
            ca_paths = [MEDIS_AUTH_CA_PATH, MEDIS_SIGN_CA_PATH, MHLW_ROOT_CA_PATH]
        for ca_path in ca_paths:
            if ca_path.exists():
                certs.append(asn1x509.Certificate.load(ca_path.read_bytes()))
        for c in self._chain_certs:
            ca = asn1x509.Certificate.load(bytes(c.dump())) if not isinstance(c, asn1x509.Certificate) else c
            if ca not in certs:
                certs.append(ca)

        if not certs:
            raise ValueError('埋め込む CA 証明書がありません')

        # CRL 取得（失敗しても証明書だけ埋め込む）
        crls = []
        from asn1crypto import crl as asn1crl
        crl_urls = self._get_crl_urls()
        for crl_url in crl_urls:
            try:
                crl_data = urllib.request.urlopen(crl_url, timeout=10).read()
                crls.append(asn1crl.CertificateList.load(crl_data))
                print(f'[bridge] CRL取得: {crl_url}', flush=True)
            except Exception as e:
                print(f'[bridge] CRL取得スキップ: {crl_url} / {e}', flush=True)

        # 署名内容を取得して VRI エントリを紐づける
        r = PdfFileReader(BytesIO(signed_bytes))
        sig = r.embedded_signatures[0]
        sig_contents = sig.pkcs7_content.hex().encode('ascii')

        # DSS にインクリメンタル追加（in-place で out_stream に書き込む）
        out_stream = BytesIO(signed_bytes)
        DocumentSecurityStore.add_dss(
            output_stream = out_stream,
            sig_contents  = sig_contents,
            certs         = certs,
            crls          = crls if crls else None,
        )
        out_stream.seek(0)
        return out_stream.read()

    def close(self) -> None:
        if self._ctx:
            try:
                self._ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._ctx = None
