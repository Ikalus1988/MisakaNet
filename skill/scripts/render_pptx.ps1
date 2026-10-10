param(
    [Parameter(Mandatory=$true)][string]$InFile,
    [Parameter(Mandatory=$true)][string]$OutDir,
    [int]$Dpi = 144
)

# Ensure output directory exists
if (!(Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

# Helper function to clean up COM objects
function Release-ComObject {
    param([object]$obj)
    if ($obj -ne $null) {
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($obj) | Out-Null
    }
}

# Try PowerPoint COM first
$ppApp = $null
$presentation = $null
try {
    Write-Host "Attempting to render with PowerPoint COM..."
    $ppApp = New-Object -ComObject PowerPoint.Application
    $ppApp.Visible = [Microsoft.Office.Core.MsoTriState]::msoFalse

    # Open the presentation (read‑only, no window)
    $presentation = $ppApp.Presentations.Open(
        $InFile,
        [Microsoft.Office.Core.MsoTriState]::msoFalse, # ReadOnly
        [Microsoft.Office.Core.MsoTriState]::msoFalse, # Untitled
        [Microsoft.Office.Core.MsoTriState]::msoFalse  # WithWindow
    )

    $slideCount = $presentation.Slides.Count
    Write-Host "Rendering $slideCount slide(s) with PowerPoint COM..."

    for ($i = 1; $i -le $slideCount; $i++) {
        $slide = $presentation.Slides.Item($i)
        $outputPath = Join-Path $OutDir ("slide{i}.png")
        # Export the
