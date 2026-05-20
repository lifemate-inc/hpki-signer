param(
    [Parameter(Mandatory = $true)]
    [string]$OutPath,
    [string]$WindowTitle = "",
    [int]$DelaySeconds = 0
)

if ($DelaySeconds -gt 0) { Start-Sleep -Seconds $DelaySeconds }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$src = @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Drawing;

public class WinApi {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc enumProc, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);

    private static string _needle;
    private static IntPtr _result;
    private static bool _enum(IntPtr hWnd, IntPtr lParam) {
        if (!IsWindowVisible(hWnd)) return true;
        var sb = new StringBuilder(512);
        GetWindowTextW(hWnd, sb, 512);
        var t = sb.ToString();
        if (!string.IsNullOrEmpty(t) && t.IndexOf(_needle, StringComparison.OrdinalIgnoreCase) >= 0) {
            _result = hWnd;
            return false;
        }
        return true;
    }
    public static IntPtr FindWindowByPartialTitle(string partial) {
        _needle = partial;
        _result = IntPtr.Zero;
        EnumWindows(new EnumProc(_enum), IntPtr.Zero);
        return _result;
    }

    public static Bitmap CaptureWindow(IntPtr hWnd) {
        RECT rect;
        GetWindowRect(hWnd, out rect);
        int w = rect.Right - rect.Left;
        int h = rect.Bottom - rect.Top;
        if (w <= 0 || h <= 0) return null;
        var bmp = new Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bmp)) {
            IntPtr hdc = g.GetHdc();
            PrintWindow(hWnd, hdc, 0x02);
            g.ReleaseHdc(hdc);
        }
        return bmp;
    }
}
"@

Add-Type -TypeDefinition $src -ReferencedAssemblies "System.Windows.Forms.dll","System.Drawing.dll"

if ($WindowTitle) {
    $hwnd = [WinApi]::FindWindowByPartialTitle($WindowTitle)
    if ($hwnd -ne [IntPtr]::Zero) {
        Write-Host "Found window: $WindowTitle"
        if ([WinApi]::IsIconic($hwnd)) {
            [WinApi]::ShowWindow($hwnd, 9) | Out-Null
            Start-Sleep -Milliseconds 400
        }
        $bmp = [WinApi]::CaptureWindow($hwnd)
        if ($null -ne $bmp) {
            $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
            Write-Host ("Saved (PrintWindow): {0} ({1}x{2})" -f $OutPath, $bmp.Width, $bmp.Height)
            $bmp.Dispose()
            exit 0
        }
    } else {
        Write-Host ("Window not found: {0}" -f $WindowTitle)
    }
}

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Host ("Saved (CopyFromScreen): {0} ({1}x{2})" -f $OutPath, $screen.Width, $screen.Height)
