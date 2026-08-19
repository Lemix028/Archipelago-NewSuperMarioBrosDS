param(
    [string]$DevkitArm = "$PSScriptRoot\..\..\..\dev\nsmbds\toolchain\devkitARM",
    [string]$OutputDirectory = "$PSScriptRoot\build",
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'

$assembler = Join-Path $DevkitArm 'bin\arm-none-eabi-as.exe'
$linker = Join-Path $DevkitArm 'bin\arm-none-eabi-ld.exe'
$objcopy = Join-Path $DevkitArm 'bin\arm-none-eabi-objcopy.exe'

foreach ($tool in @($assembler, $linker, $objcopy)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "Required devkitARM tool was not found: $tool"
    }
}

$resolvedSourceRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
if ($resolvedOutput -eq $resolvedSourceRoot) {
    throw 'The build output must not overwrite the native source directory.'
}
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

function Build-ArmBinary {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$LinkAddress
    )

    $source = Join-Path $PSScriptRoot "asm\$Name.s"
    $object = Join-Path $resolvedOutput "$Name.o"
    $elf = Join-Path $resolvedOutput "$Name.elf"
    $binary = Join-Path $resolvedOutput "$Name.bin"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Assembly source was not found: $source"
    }

    & $assembler -mcpu=arm946e-s -o $object $source
    if ($LASTEXITCODE -ne 0) { throw "ARM assembler failed for $Name." }
    & $linker "-Ttext=$LinkAddress" -o $elf $object
    if ($LASTEXITCODE -ne 0) { throw "ARM linker failed for $Name." }
    & $objcopy -O binary $elf $binary
    if ($LASTEXITCODE -ne 0) { throw "ARM objcopy failed for $Name." }

    Write-Output "Built $Name at $binary"
}

Build-ArmBinary -Name 'star_coin_gate_hook' -LinkAddress '0x020EDFC4'
Build-ArmBinary -Name 'star_coin_currency_hook' -LinkAddress '0x02002EC0'
Build-ArmBinary -Name 'powerup_license_hook' -LinkAddress '0x02002F00'

& (Join-Path $PSScriptRoot 'build_marker.ps1') -DevkitArm $DevkitArm -OutputDirectory $resolvedOutput
if ($LASTEXITCODE -ne 0) { throw 'Patch marker build failed.' }

Write-Output 'Verifying the generated hook bytes against the checked-in metadata...'
& $Python (Join-Path $PSScriptRoot 'verify_native_hooks.py') --build-directory $resolvedOutput
if ($LASTEXITCODE -ne 0) { throw 'Native hook verification failed.' }
