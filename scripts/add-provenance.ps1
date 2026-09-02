<#
.SYNOPSIS
    Add provenance metadata to contrib lessons without it.

.DESCRIPTION
    Scans lessons/contrib/ for .md files without provenance block.
    Infers provenance from frontmatter source, git history, and known contributors.
    Processes first BatchSize lessons by default.

.PARAMETER BatchSize
    Number of lessons to process. Default: 30.

.PARAMETER DryRun
    Show what would be done without writing files.

.EXAMPLE
    .\add-provenance.ps1
    .\add-provenance.ps1 -BatchSize 50
    .\add-provenance.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [int]$BatchSize = 30,
    [switch]$DryRun
)

# Auto-detect repo root from script location
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$contribDir = Join-Path $repoRoot "lessons\contrib"

# Get all .md files in contrib (exclude README)
$allLessons = Get-ChildItem -Path $contribDir -Filter "*.md" | Where-Object { $_.Name -ne "README.md" }

# Filter out lessons that already have provenance
$lessonsNeedingProvenance = @()
foreach ($lesson in $allLessons) {
    $content = Get-Content $lesson.FullName -Raw
    if ($content -notmatch "provenance:") {
        $lessonsNeedingProvenance += $lesson
    }
}

Write-Host "Total contrib lessons: $($allLessons.Count)"
Write-Host "Lessons with provenance: $($allLessons.Count - $lessonsNeedingProvenance.Count)"
Write-Host "Lessons needing provenance: $($lessonsNeedingProvenance.Count)"
Write-Host "Processing batch of $BatchSize..."
Write-Host ""

$processed = 0
$results = [System.Collections.ArrayList]::new()

$lessonBatch = $lessonsNeedingProvenance[0..([Math]::Min($BatchSize-1, $lessonsNeedingProvenance.Count-1))]

foreach ($lesson in $lessonBatch) {
    $processed++
    Write-Host "[$processed/$([Math]::Min($BatchSize, $lessonsNeedingProvenance.Count))] $($lesson.Name)"

    try {
        $content = Get-Content $lesson.FullName -Raw
        $lines = $content -split "`n"

        # Extract frontmatter
        $inFrontmatter = $false
        $frontmatterEnd = -1
        $source = ""
        $created = ""
        $contributor = ""

        for ($i = 0; $i -lt $lines.Count; $i++) {
            $line = $lines[$i].Trim()

            # Detect frontmatter start (YAML or JSON)
            if ($i -eq 0 -and ($line -eq "---" -or $line -eq "{")) {
                $inFrontmatter = $true
                if ($line -eq "{") {
                    # JSON frontmatter
                    $jsonContent = ""
                    for ($j = $i; $j -lt $lines.Count; $j++) {
                        $jsonContent += $lines[$j]
                        if ($lines[$j].Trim() -eq "}") {
                            $frontmatterEnd = $j
                            break
                        }
                    }
                    try {
                        $json = $jsonContent | ConvertFrom-Json
                        $source = $json.source
                        $created = $json.created
                        $contributor = $json.domain_expert
                    } catch {
                        Write-Warning "Failed to parse JSON frontmatter in $($lesson.Name): $_"
                    }
                    break
                }
            }

            # Detect frontmatter end (YAML)
            if ($inFrontmatter -and $line -eq "---" -and $i -gt 0) {
                $frontmatterEnd = $i
                break
            }

            # Extract fields from YAML
            if ($inFrontmatter) {
                if ($line -match "^source:\s*""?([^""\s]+)""?\s*$") {
                    $source = $matches[1]
                }
                if ($line -match "^created:\s*""?(\d{4}-\d{2}-\d{2})""?\s*$") {
                    $created = $matches[1]
                }
                if ($line -match "^domain_expert:\s*""?([^""\s]+)""?\s*$") {
                    $contributor = $matches[1]
                }
            }
        }

        # Determine provenance source type
        $provenanceSource = "internal"  # default
        if ($source -match "github" -or $source -match "pr" -or $source -match "pull request") {
            $provenanceSource = "github-pr"
        } elseif ($source -match "mcp" -or $source -match "intake") {
            $provenanceSource = "mcp-intake"
        } elseif ($source -match "colleague" -or $source -match "memory") {
            $provenanceSource = "colleague-memory"
        } elseif ($source -match "forum" -or $source -match "robot-forum" -or $source -match "segmentfault" -or $source -match "v2ex") {
            $provenanceSource = "colleague-memory"  # forum posts are peer-shared
        } elseif ($source -match "zsxh" -or $source -match "pdl" -or $source -match "codex" -or $source -match "claude") {
            $provenanceSource = "github-pr"  # known contributors
        }

        # Get git history
        $gitResult = & git log --follow --format='%an|%ai' -- "lessons/contrib/$($lesson.Name)" 2>$null
        $gitAuthor = ""
        $gitDate = ""
        if ($gitResult) {
            $lastCommit = ($gitResult | Select-Object -Last 1) -split "\|"
            $gitAuthor = $lastCommit[0]
            if ($lastCommit[1] -match "^(\d{4}-\d{2}-\d{2})") {
                $gitDate = $matches[1]
            }
        }

        # Use contributor from frontmatter, fallback to git author
        if (-not $contributor -and $gitAuthor) {
            $contributor = $gitAuthor
        }
        if (-not $contributor) {
            $contributor = "unknown"
        }

        # Use created date, fallback to git date
        $mergedAt = if ($created) { $created } elseif ($gitDate) { $gitDate } else { "2026-07-01" }

        # Determine evidence type
        $evidence = "post-publication"  # default for forum/colleague sources
        if ($provenanceSource -eq "github-pr") {
            $evidence = "pr-merged"
        } elseif ($provenanceSource -eq "mcp-intake") {
            $evidence = "pre-ingest-reuse"
        }

        # Build provenance block
        $provenanceBlock = @"

provenance:
  source: "$provenanceSource"
  contributor: "$contributor"
  merged_at: "$mergedAt"
  evidence: "$evidence"
"@

        # Insert provenance before closing frontmatter
        $newContent = $content

        if ($content -match "^---") {
            # YAML frontmatter - insert before closing ---
            $newContent = $content -replace "(---\s*\n)", "`$1$provenanceBlock`n", 1
        } elseif ($content -match "^\{") {
            # JSON frontmatter - convert to YAML
            Write-Host "  Note: Converting JSON frontmatter to YAML (not implemented yet)"
            continue
        }

        # Write back (unless dry run)
        if (-not $DryRun) {
            Set-Content -Path $lesson.FullName -Value $newContent -NoNewline
        }

        $null = $results.Add([PSCustomObject]@{
            File = $lesson.Name
            Source = $source
            Contributor = $contributor
            MergedAt = $mergedAt
            ProvenanceSource = $provenanceSource
            Evidence = $evidence
        })

        Write-Host "  -> Added provenance: $provenanceSource | $contributor | $mergedAt | $evidence"
    } catch {
        Write-Error "Failed to process $($lesson.Name): $_"
    }
}

Write-Host ""
Write-Host "=== Summary ==="
Write-Host "Processed: $processed lessons"
if ($DryRun) {
    Write-Host "(Dry run - no files were modified)"
}
Write-Host ""
Write-Host "Provenance sources:"
$results | Group-Object ProvenanceSource | ForEach-Object { Write-Host "  $($_.Name): $($_.Count)" }
Write-Host ""
Write-Host "Evidence types:"
$results | Group-Object Evidence | ForEach-Object { Write-Host "  $($_.Name): $($_.Count)" }
