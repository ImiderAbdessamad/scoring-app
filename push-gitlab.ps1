<#
  Publie backend/ et/ou frontend/ de scoring-app vers leurs dépôts GitLab.

  Chaque dossier est extrait avec son historique (git subtree split), puis
  rattaché à la branche main de GitLab par un commit de fusion : le push reste
  une avance rapide, accepté par la branche protégée (pas de push forcé).

  Usage (depuis la racine de scoring-app, après git push origin main) :
    .\push-gitlab.ps1              # backend + frontend
    .\push-gitlab.ps1 backend
    .\push-gitlab.ps1 frontend
#>
param(
  [ValidateSet('all', 'backend', 'frontend')]
  [string]$Target = 'all'
)

$ErrorActionPreference = 'Stop'

$Repos = [ordered]@{
  backend  = 'https://gitlab.wafabail.ma/ia/scoring/backend.git'
  frontend = 'https://gitlab.wafabail.ma/ia/scoring/frontend.git'
}

function Invoke-Git {
  $output = & git @args
  if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') a échoué." }
  return $output
}

Set-Location (Invoke-Git rev-parse --show-toplevel)

$branch = Invoke-Git rev-parse --abbrev-ref HEAD
if ($branch -ne 'main') { throw "Placez-vous sur main (branche actuelle : $branch)." }

$source = Invoke-Git rev-parse --short HEAD
$names = if ($Target -eq 'all') { @($Repos.Keys) } else { @($Target) }

foreach ($name in $names) {
  $url = $Repos[$name]
  Write-Host "`n== $name -> $url" -ForegroundColor Cyan

  # Fichiers suivis seulement : les dossiers locaux non versionnés (.claude, .venv…) ne comptent pas.
  if (Invoke-Git status --porcelain --untracked-files=no -- $name) {
    Write-Warning "$name/ contient des modifications non commitées : elles ne seront pas publiées."
  }

  $split = (Invoke-Git subtree split --prefix=$name) | Select-Object -Last 1
  Invoke-Git fetch $url main | Out-Null
  $remote = Invoke-Git rev-parse FETCH_HEAD

  if (-not $split -or -not $remote) { throw "Extraction ou récupération de $name impossible : rien n'est poussé." }

  if ((Invoke-Git rev-parse "$split^{tree}") -eq (Invoke-Git rev-parse "$remote^{tree}")) {
    Write-Host "Déjà à jour sur GitLab." -ForegroundColor Green
    continue
  }

  $merge = Invoke-Git commit-tree "$split^{tree}" -p $remote -p $split -m "sync: $name depuis scoring-app@$source"
  if (-not $merge) { throw "Commit de synchronisation non créé : rien n'est poussé." }

  Invoke-Git push $url "${merge}:refs/heads/main"
  Write-Host "Publié : $merge" -ForegroundColor Green
}
