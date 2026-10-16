Add-Type -AssemblyName System.Drawing
$iconDirectory = Join-Path $PSScriptRoot '..\pogocoordinates-monitor\icons'
[System.IO.Directory]::CreateDirectory($iconDirectory) | Out-Null
$canvas = [System.Drawing.Bitmap]::new(512,512)
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)
$navy = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#102B2A'))
$mint = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#62E9AF'))
$white = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#F1FFF9'))
$red = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#FF6774'))
$outline = [System.Drawing.Pen]::new($navy,18)
$ring = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#388B76'),9)
$sweep = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#62E9AF'),15)
$sweep.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$sweep.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$graphics.FillEllipse($navy,8,8,496,496)
$graphics.DrawEllipse($ring,54,54,404,404)
$graphics.DrawEllipse($ring,108,108,296,296)
$graphics.DrawArc($sweep,54,54,404,404,215,95)
$graphics.DrawLine($sweep,256,256,392,120)
$graphics.FillEllipse($mint,375,102,36,36)
$graphics.FillEllipse($mint,91,318,28,28)
$graphics.FillEllipse($white,144,144,224,224)
$graphics.FillPie($red,144,144,224,224,180,180)
$graphics.DrawEllipse($outline,144,144,224,224)
$graphics.DrawLine($outline,147,256,365,256)
$graphics.FillEllipse($navy,211,211,90,90)
$graphics.FillEllipse($white,229,229,54,54)
$graphics.FillEllipse($mint,242,242,28,28)
foreach ($size in @(16,32,48,128,512)) {
  $icon = [System.Drawing.Bitmap]::new($size,$size)
  $scaled = [System.Drawing.Graphics]::FromImage($icon)
  $scaled.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $scaled.DrawImage($canvas,0,0,$size,$size)
  $icon.Save((Join-Path $iconDirectory "icon-$size.png"),[System.Drawing.Imaging.ImageFormat]::Png)
  $scaled.Dispose()
  $icon.Dispose()
}
foreach ($resource in @($graphics,$canvas,$navy,$mint,$white,$red,$outline,$ring,$sweep)) { $resource.Dispose() }
