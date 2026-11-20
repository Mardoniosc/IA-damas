<#
.SYNOPSIS
  Reproducible local build of Scan 3.1 (Fabien Letouzey, GPL-3.0) from source with MSVC.

.DESCRIPTION
  - Clones https://github.com/rhalbersma/scan (mirror of Scan 3.1) at a pinned commit into
    <repo>/engines/scan31/src (git-ignored; never committed or redistributed - ADR-004).
  - Compiles with the newest Visual Studio C++ toolset found by vswhere.
  - Produces <repo>/engines/scan31/bin/{scan.exe, scan.ini, data/, BUILD-INFO.txt}.
  - The prebuilt scan.exe shipped inside the mirror is NOT used.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/engines/build_scan.ps1
#>
param(
    [string]$Commit = "7aae17e7b7bfc47744601afb1ee7655e18983ce5",
    [string]$Repo = "https://github.com/rhalbersma/scan.git"
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$base = Join-Path $root "engines\scan31"
$src = Join-Path $base "src"
$bin = Join-Path $base "bin"
$obj = Join-Path $base "obj"

if (-not (Test-Path $src)) {
    git clone --quiet $Repo $src
}
git -C $src fetch --quiet origin
git -C $src checkout --quiet $Commit
$head = (git -C $src rev-parse HEAD).Trim()
if ($head -ne $Commit) { throw "checkout mismatch: $head" }

$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw "No Visual Studio with the x64 C++ toolset found" }
$vcvars = Join-Path $vs "VC\Auxiliary\Build\vcvars64.bat"

New-Item -ItemType Directory -Force $bin, $obj | Out-Null
$flags = "/nologo /O2 /Oi /GL /EHsc /std:c++14 /GR- /DNDEBUG /MT /W3"
$cmd = "call `"$vcvars`" >nul && cd /d `"$src\src`" && cl $flags /Fo`"$obj\\`" *.cpp /Fe`"$bin\scan.exe`" /link /LTCG ws2_32.lib"
cmd /c $cmd
if ($LASTEXITCODE -ne 0) { throw "compilation failed ($LASTEXITCODE)" }

Copy-Item (Join-Path $src "scan.ini") $bin -Force
Copy-Item (Join-Path $src "data") $bin -Recurse -Force
Copy-Item (Join-Path $src "license.txt") $bin -Force

$clver = (cmd /c "call `"$vcvars`" >nul && cl 2>&1" | Select-Object -First 1)
$sha = (Get-FileHash (Join-Path $bin "scan.exe") -Algorithm SHA256).Hash
@"
Scan 3.1 built locally from source (GPL-3.0; see license.txt)
source:   $Repo
commit:   $head
compiler: $clver
flags:    $flags /link /LTCG ws2_32.lib
built:    $(Get-Date -Format o)
sha256:   $sha
"@ | Set-Content -Encoding utf8 (Join-Path $bin "BUILD-INFO.txt")
Get-Content (Join-Path $bin "BUILD-INFO.txt")
