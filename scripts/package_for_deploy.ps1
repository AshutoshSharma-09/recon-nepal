$exclude = @(
    "node_modules", 
    ".next", 
    ".venv", 
    "__pycache__", 
    ".git", 
    ".vscode", 
    "*.log", 
    "*.zip"
)

$source = "$PSScriptRoot\.."
$destination = "$PSScriptRoot\..\pms-recon-update.zip"

if (Test-Path $destination) {
    Remove-Item $destination -Force -ErrorAction SilentlyContinue
}

Write-Host "Packaging files to $destination..."

# Using standard Compress-Archive
# Note: Wildcards exclude standard ignored folders if specified carefully, 
# but Compress-Archive is simple. We may need to be specific.

# Better approach: Copy to temp, clean, then zip.
$tempDir = "$PSScriptRoot\..\temp_deploy"
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -Type Directory -Path $tempDir | Out-Null

# Copy Backend
New-Item -Type Directory -Path "$tempDir\backend" | Out-Null
Copy-Item "$source\backend\*" "$tempDir\backend" -Recurse -Exclude "venv", "__pycache__", "*.pyc"

# Copy Frontend (Exclude node_modules and .next)
New-Item -Type Directory -Path "$tempDir\frontend" | Out-Null
Copy-Item "$source\frontend\*" "$tempDir\frontend" -Recurse -Exclude "node_modules", ".next"

# Copy Scripts
New-Item -Type Directory -Path "$tempDir\scripts" | Out-Null
Copy-Item "$source\scripts\*" "$tempDir\scripts" -Recurse

# Copy Configs
Copy-Item "$source\docker-compose.yml" "$tempDir"
if (Test-Path "$source\nginx") {
    New-Item -Type Directory -Path "$tempDir\nginx" | Out-Null
    Copy-Item "$source\nginx\*" "$tempDir\nginx" -Recurse
}

# NOTE: We do NOT copy .env. The VM has its own production .env.
# Copy-Item "$source\.env" "$tempDir" -ErrorAction SilentlyContinue

Write-Host "Compressing..."
Start-Sleep -Seconds 2
Compress-Archive -Path "$tempDir\*" -DestinationPath $destination

# Cleanup
Remove-Item $tempDir -Recurse -Force

Write-Host "Done! Upload 'pms-recon-update.zip' to your VM."
