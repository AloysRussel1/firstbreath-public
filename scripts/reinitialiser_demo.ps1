<#
.SYNOPSIS
  Remet la démo FirstBreath à zéro : supprime le stockage du backend (base SQLite et photos reçues).

.DESCRIPTION
  Supprime le dossier de stockage du backend : backend\storage, ou le dossier indiqué par la variable
  d'environnement FIRSTBREATH_DATA_DIR, ou celui passé avec -Dossier.
  Ne touche jamais à data\ (registre du défi), au cache de l'extraction (extraction\cache, evaluation\cache)
  ni à .env (le script ne le lit pas). N'arrête aucun processus.

  Avant : arrêtez le serveur (Ctrl+C dans son terminal), sinon la base est verrouillée.
  Après : relancez le serveur, puis effacez les données de l'appareil dans l'application
  (Réglages > Effacer les données de l'appareil), pour vider aussi le coffre local du navigateur.

.PARAMETER Dossier
  Dossier de stockage à supprimer. Si FIRSTBREATH_DATA_DIR est défini seulement dans .env, passez-le ici.

.EXAMPLE
  .\scripts\reinitialiser_demo.ps1
.EXAMPLE
  .\scripts\reinitialiser_demo.ps1 -Dossier D:\firstbreath-donnees
#>
param([string]$Dossier = "")

$ErrorActionPreference = "Stop"
$racine = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $Dossier) {
  if ($env:FIRSTBREATH_DATA_DIR) { $Dossier = $env:FIRSTBREATH_DATA_DIR } else { $Dossier = Join-Path $racine "backend\storage" }
}
if (-not [System.IO.Path]::IsPathRooted($Dossier)) { $Dossier = Join-Path $racine $Dossier }
$cible = [System.IO.Path]::GetFullPath($Dossier).TrimEnd('\')

Write-Host ""
Write-Host "Réinitialisation de la démo FirstBreath" -ForegroundColor Cyan
Write-Host "  Stockage du backend : $cible"
Write-Host "  Avant : arrêtez le serveur (Ctrl+C dans son terminal). Ce script n'arrête aucun processus."
Write-Host ""

if (-not (Test-Path -LiteralPath $cible)) {
  Write-Host "Rien à supprimer : ce dossier n'existe pas (la démo est déjà vide côté serveur)."
  Write-Host "Pensez à effacer les données de l'appareil dans Réglages."
  exit 0
}

# Garde-fous : jamais data\, le cache d'extraction, .env, la racine du dépôt ou d'un disque.
function Contient([string]$parent, [string]$enfant) {
  $p = $parent.TrimEnd('\') + '\'
  return ($enfant.TrimEnd('\') + '\').StartsWith($p, [System.StringComparison]::OrdinalIgnoreCase)
}
$proteges = @("data", "extraction\cache", "evaluation\cache", ".env") | ForEach-Object { Join-Path $racine $_ }
$refus = $null
if ($cible -eq [System.IO.Path]::GetPathRoot($cible).TrimEnd('\')) { $refus = "c'est la racine d'un disque" }
elseif (Contient $cible $racine) { $refus = "ce dossier contient le dépôt" }
else {
  foreach ($p in $proteges) {
    if ((Contient $p $cible) -or (Contient $cible $p)) { $refus = "ce dossier touche $p" }
  }
}
if (-not $refus) {
  # Un stockage du backend ne contient que la base SQLite et le dossier images.
  $inattendus = Get-ChildItem -LiteralPath $cible -Force | Where-Object { $_.Name -notmatch '^(firstbreath\.sqlite3(-wal|-shm|-journal)?|images)$' }
  if ($inattendus) { $refus = "il contient d'autres fichiers que le stockage du backend : " + (($inattendus | Select-Object -First 5 | ForEach-Object Name) -join ", ") }
}
if ($refus) {
  Write-Host "Refusé : $refus. Rien n'a été supprimé." -ForegroundColor Red
  exit 1
}

$photos = 0
if (Test-Path -LiteralPath (Join-Path $cible "images")) { $photos = @(Get-ChildItem -LiteralPath (Join-Path $cible "images") -File).Count }
Write-Host "Seront supprimés : la base des dossiers (firstbreath.sqlite3) et $photos photo(s) reçue(s)."
$reponse = Read-Host "Tapez OUI pour confirmer"
if ($reponse -cne "OUI") {
  Write-Host "Annulé. Rien n'a été supprimé."
  exit 0
}

try {
  Remove-Item -LiteralPath $cible -Recurse -Force
} catch {
  Write-Host "Échec : $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Le serveur tourne-t-il encore ? Arrêtez-le (Ctrl+C dans son terminal), puis relancez ce script."
  exit 1
}

Write-Host ""
Write-Host "Stockage du backend supprimé. Le serveur recréera une base vide au prochain démarrage." -ForegroundColor Green
Write-Host "Ensuite : relancez le serveur, puis, dans l'application, Réglages > Effacer les données de l'appareil."
