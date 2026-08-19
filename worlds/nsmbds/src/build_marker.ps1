param(
    [string]$DevkitArm = "$PSScriptRoot\..\..\..\dev\nsmbds\toolchain\devkitARM",
    [string]$OutputDirectory = "$PSScriptRoot\build"
)

$ErrorActionPreference = 'Stop'

$assembler = Join-Path $DevkitArm 'bin\arm-none-eabi-as.exe'
$objcopy = Join-Path $DevkitArm 'bin\arm-none-eabi-objcopy.exe'
$source = Join-Path $PSScriptRoot 'asm\patch_marker.s'
$object = Join-Path $OutputDirectory 'patch_marker.o'
$binary = Join-Path $OutputDirectory 'patch_marker.bin'

if (-not (Test-Path -LiteralPath $assembler)) {
    throw "ARM assembler not found: $assembler"
}
if (-not (Test-Path -LiteralPath $objcopy)) {
    throw "ARM objcopy not found: $objcopy"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& $assembler -mcpu=arm946e-s -o $object $source
if ($LASTEXITCODE -ne 0) { throw 'ARM assembler failed for the patch marker.' }
& $objcopy -O binary $object $binary
if ($LASTEXITCODE -ne 0) { throw 'ARM objcopy failed for the patch marker.' }

$bytes = [System.IO.File]::ReadAllBytes($binary)
$hex = [System.BitConverter]::ToString($bytes).Replace('-', ' ')
Write-Output '=== NSMBDS Patch Marker Build ==='
Write-Output "object: $object"
Write-Output "binary: $binary"
Write-Output "size: $($bytes.Length)"
Write-Output "bytes: $hex"
