param(
    [string]$Owner = "amin-pourmand",
    [string]$Repo = "cinescene",
    [string]$Branch = "main",
    [string]$PagesBranch = "gh-pages"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {
    $expectedRemote = "https://github.com/$Owner/$Repo.git"
    $remote = git remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $remote.TrimEnd('/') -ne $expectedRemote) {
        throw "origin must point to $expectedRemote. The publisher does not replace repository remotes."
    }
    $dirty = git status --porcelain -- docs
    if ($dirty) { throw "Commit docs/ changes before publishing so the deployed index matches the source commit." }

    $python = Join-Path $root ".venv/Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
    & $python scripts/validate_public_index.py
    if ($LASTEXITCODE -ne 0) { throw "Catalog/index validation failed. Rebuild the public hybrid index first." }

    git push origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "Source push failed." }
    $split = git subtree split --prefix=docs $Branch
    if ($LASTEXITCODE -ne 0) { throw "Could not derive the Pages commit." }
    git push origin "$($split.Trim()):refs/heads/$PagesBranch"
    if ($LASTEXITCODE -ne 0) { throw "Pages push failed. Inspect remote history; this script never force-pushes." }

    Write-Host "Repository: https://github.com/$Owner/$Repo"
    Write-Host "PWA: https://$($Owner.ToLower()).github.io/$Repo/"
    Write-Host "GitHub Pages must use the $PagesBranch branch, root folder. Deployment can take a few minutes."
}
finally {
    Pop-Location
}
