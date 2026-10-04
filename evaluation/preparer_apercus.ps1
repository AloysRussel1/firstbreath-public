param([string]$Destination = "$PSScriptRoot/apercus")
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$rootEval = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$regionsEval = @{
1 = @(@(110,560,1430,390), @(110,1190,1430,430))
2 = @(@(110,465,1430,70), @(90,1990,1430,220))
3 = ,@(850,175,690,100)
4 = @(@(540,310,970,450), @(540,900,970,410), @(530,1340,980,470), @(540,1840,970,120))
5 = @(@(100,405,1430,90), @(100,1090,1430,210), @(100,1390,1430,210), @(100,1640,1430,410))
6 = @(@(100,440,1430,330), @(100,1150,1430,190), @(100,1840,1430,90))
7 = @(@(100,405,1430,90), @(100,1090,1430,210), @(100,1390,1430,210), @(100,1640,1430,410))
8 = @(@(100,440,1430,330), @(100,1150,1430,190), @(100,1840,1430,90))
}
foreach ($typeEval in 1..8) {
 $regionsTypeEval = $regionsEval[$typeEval]
 $tileHeightEval = 40
 foreach ($rEval in $regionsTypeEval) { $tileHeightEval += [int]($rEval[3] * 800 / $rEval[2]) + 8 }
 foreach ($batchEval in 0..1) {
  $sheetEval = New-Object System.Drawing.Bitmap (1600, ($tileHeightEval * 3))
  $graphicsEval = [System.Drawing.Graphics]::FromImage($sheetEval)
  $graphicsEval.Clear([System.Drawing.Color]::White)
  $fontEval = New-Object System.Drawing.Font ('Arial', 18)
  foreach ($jEval in 0..4) {
   $pageEval = ($batchEval * 5 + $jEval) * 8 + $typeEval
   $patternEval = 'dossiers_specimen_10_patientes-{0:D2}*.png' -f $pageEval
   $filesEval = @(Get-ChildItem -LiteralPath "$rootEval/data/Paper Registry" -Filter $patternEval | Sort-Object Name)
   $hashesEval = @($filesEval | Get-FileHash -Algorithm SHA256 | Select-Object -ExpandProperty Hash -Unique)
   if ($hashesEval.Count -ne 1) { throw "Doublons différents page $pageEval" }
   $sourceEval = [System.Drawing.Image]::FromFile($filesEval[0].FullName)
   $xEval = ($jEval % 2) * 800
   $yEval = [int][Math]::Floor($jEval / 2) * $tileHeightEval
   $graphicsEval.DrawString("Page $pageEval", $fontEval, [System.Drawing.Brushes]::Black, $xEval, $yEval)
   $yEval += 35
   foreach ($rEval in $regionsTypeEval) {
    $hEval = [int]($rEval[3] * 800 / $rEval[2])
    $destEval = New-Object System.Drawing.Rectangle ($xEval, $yEval, 800, $hEval)
    $srcEval = New-Object System.Drawing.Rectangle ($rEval[0], $rEval[1], $rEval[2], $rEval[3])
    $graphicsEval.DrawImage($sourceEval, $destEval, $srcEval, [System.Drawing.GraphicsUnit]::Pixel)
    $yEval += $hEval + 8
   }
   $sourceEval.Dispose()
  }
  $sheetEval.Save((Join-Path $Destination "type${typeEval}_lot${batchEval}.png"), [System.Drawing.Imaging.ImageFormat]::Png)
  $graphicsEval.Dispose(); $sheetEval.Dispose(); $fontEval.Dispose()
 }
}
Write-Output '16 planches générées ; doublons vérifiés par SHA-256.'

