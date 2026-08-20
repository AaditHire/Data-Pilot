$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$targetPath = Join-Path $projectRoot ".env.local"

Write-Host "Paste your Groq API key. Input is hidden:" -ForegroundColor Cyan
$secureKey = Read-Host -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if ([string]::IsNullOrWhiteSpace($plainKey) -or -not $plainKey.StartsWith("gsk_")) {
        throw "That does not look like a Groq API key. Nothing was written."
    }

    $existingLines = if (Test-Path -LiteralPath $targetPath) {
        [IO.File]::ReadAllLines($targetPath)
    } else {
        @()
    }

    $settings = [ordered]@{
        "GROQ_API_KEY" = $plainKey
        "LLM_PROVIDER" = "groq"
        "GROQ_MODEL" = "openai/gpt-oss-20b"
    }

    $outputLines = [Collections.Generic.List[string]]::new()
    foreach ($line in $existingLines) {
        $matchedSetting = $null
        foreach ($name in $settings.Keys) {
            if ($line -match "^\s*$name\s*=") {
                $matchedSetting = $name
                break
            }
        }
        if ($null -eq $matchedSetting) {
            $outputLines.Add($line)
        }
    }
    foreach ($name in $settings.Keys) {
        $outputLines.Add("$name=$($settings[$name])")
    }

    [IO.File]::WriteAllLines($targetPath, $outputLines, [Text.UTF8Encoding]::new($false))
    Write-Host "Groq configuration saved to .env.local." -ForegroundColor Green
} finally {
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    $plainKey = $null
    $secureKey = $null
}
