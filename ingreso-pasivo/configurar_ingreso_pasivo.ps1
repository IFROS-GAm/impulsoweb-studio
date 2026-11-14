<#
.SYNOPSIS
    Verifica e inicia el registro/descarga de aplicaciones de ingreso pasivo por ancho de banda:
    Grass, Pawns.app y Honeygain.
#>

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURADOR DE INGRESO PASIVO (SIN DESGASTE DE PC)     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$apps = @(
    @{
        Nombre = "Grass (Extension / Desktop Node)"
        Rutas = @(
            "$env:LOCALAPPDATA\Programs\Grass\Grass.exe",
            "$env:LOCALAPPDATA\Grass\Grass.exe"
        )
        Proceso = "Grass"
        UrlRegistro = "https://app.getgrass.io/register"
        UrlDescarga = "https://app.getgrass.io/dashboard/store/item/desktop"
        Nota = "No consume CPU/GPU; comparte ancho de banda residual para entrenamiento de IA."
    },
    @{
        Nombre = "Pawns.app (App de escritorio)"
        Rutas = @(
            "$env:LOCALAPPDATA\Programs\pawns-app\Pawns.app.exe",
            "$env:ProgramFiles\Pawns.app\Pawns.app.exe",
            "${env:ProgramFiles(x86)}\Pawns.app\Pawns.app.exe"
        )
        Proceso = "Pawns"
        UrlRegistro = "https://pawns.app/"
        UrlDescarga = "https://pawns.app/download/"
        Nota = "Paga en USD (PayPal/Bitcoin/Giftcards) desde $5 USD de minimo."
    },
    @{
        Nombre = "Honeygain"
        Rutas = @(
            "${env:ProgramFiles(x86)}\Honeygain\Honeygain.exe",
            "$env:ProgramFiles\Honeygain\Honeygain.exe",
            "$env:LOCALAPPDATA\Honeygain\Honeygain.exe"
        )
        Proceso = "Honeygain"
        UrlRegistro = "https://www.honeygain.com/"
        UrlDescarga = "https://www.honeygain.com/download/"
        Nota = "Compatible con Windows en segundo plano; usa Content Delivery para ganar mas."
    }
)

Write-Host "1. Verificando estado en esta computadora..." -ForegroundColor Yellow
foreach ($app in $apps) {
    $encontrado = $false
    foreach ($r in $app.Rutas) {
        if (Test-Path $r) {
            $encontrado = $true
            Write-Host "  [INSTALADO] $($app.Nombre) -> $r" -ForegroundColor Green
            break
        }
    }
    $proc = Get-Process -Name "*$($app.Proceso)*" -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "  [ACTIVO]    $($app.Nombre) esta corriendo en segundo plano." -ForegroundColor Green
    } elseif (-not $encontrado) {
        Write-Host "  [PENDIENTE] $($app.Nombre) no detectado." -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "Por seguridad, cada plataforma requiere crear tu cuenta con tu correo" -ForegroundColor Gray
Write-Host "y activar la sesion una sola vez en este equipo." -ForegroundColor Gray
Write-Host ""
Write-Host "Opciones:" -ForegroundColor Cyan
Write-Host "  [1] Abrir paginas oficiales de registro y descarga (Grass + Pawns.app + Honeygain)"
Write-Host "  [2] Abrir solo Grass"
Write-Host "  [3] Abrir solo Pawns.app"
Write-Host "  [4] Abrir solo Honeygain"
Write-Host "  [S] Salir"
Write-Host ""

$choice = Read-Host "Elige una opcion (1-4 o S)"
switch ($choice.ToUpper()) {
    "1" {
        Start-Process "https://app.getgrass.io/register"
        Start-Process "https://pawns.app/download/"
        Start-Process "https://www.honeygain.com/download/"
        Write-Host "Se abrieron las 3 paginas oficiales en tu navegador." -ForegroundColor Green
    }
    "2" {
        Start-Process "https://app.getgrass.io/register"
        Start-Process "https://app.getgrass.io/dashboard/store/item/desktop"
    }
    "3" {
        Start-Process "https://pawns.app/"
        Start-Process "https://pawns.app/download/"
    }
    "4" {
        Start-Process "https://www.honeygain.com/"
        Start-Process "https://www.honeygain.com/download/"
    }
    default {
        Write-Host "Saliendo sin abrir paginas." -ForegroundColor Gray
    }
}
