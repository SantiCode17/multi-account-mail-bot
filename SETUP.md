# 📬 Inbox Bridge — Guía de Configuración

---

## 1. Crear Bot de Telegram

1. Abre **[@BotFather](https://t.me/BotFather)** en Telegram
2. Envía `/newbot` → elige un nombre → elige un usuario (debe terminar en `bot`)
3. **Copia el token** que te da (ejemplo: `8641449158:AAH-gzI76Kz...`)

## 2. Obtener tu Chat ID

1. Abre **[@userinfobot](https://t.me/userinfobot)** en Telegram
2. Envía `/start`
3. **Copia el número** de `Id` (ejemplo: `1792370231`)

## 3. Configurar `.env`

Edita el archivo `.env` en la raíz del proyecto y pon tus datos:

```env
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
CHECK_INTERVAL_SECONDS=10
```

## 4. Configurar cuentas de correo

Edita `config/accounts.json`. Cada cuenta necesita una **contraseña de aplicación** (no tu contraseña normal).

### Estructura

```json
{
  "accounts": [
    {
      "email": "tu_correo@gmail.com",
      "password": "contraseña de aplicación",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

### Ejemplo con varias cuentas

```json
{
  "accounts": [
    {
      "email": "mi_correo@gmail.com",
      "password": "abcd efgh ijkl mnop",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    },
    {
      "email": "mi_correo@hotmail.com",
      "password": "xxxx yyyy zzzz wwww",
      "imap_server": "outlook.office365.com",
      "imap_port": 993,
      "use_ssl": true
    },
    {
      "email": "mi_correo@yahoo.com",
      "password": "aaaa bbbb cccc dddd",
      "imap_server": "imap.mail.yahoo.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

> ⚠️ La última cuenta **NO** lleva coma después del `}`

---

## 5. Configuración por proveedor

### Gmail (`@gmail.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.gmail.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
> Requiere verificación en 2 pasos activada previamente

### Outlook / Hotmail / Live (`@outlook.com`, `@hotmail.com`, `@live.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `outlook.office365.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [account.live.com/proofs/AppPassword](https://account.live.com/proofs/AppPassword)

### Yahoo (`@yahoo.com`, `@yahoo.es`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.mail.yahoo.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [login.yahoo.com/account/security](https://login.yahoo.com/account/security) → Generar contraseña de app

### iCloud (`@icloud.com`, `@me.com`, `@mac.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.mail.me.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [appleid.apple.com](https://appleid.apple.com/account/manage) → Contraseñas específicas de app

### Zoho (`@zoho.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.zoho.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [accounts.zoho.com/home#security/app_password](https://accounts.zoho.com/home#security/app_password)

### ProtonMail (`@proton.me`, `@protonmail.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `127.0.0.1` |
| Puerto | `1143` |
| SSL | `false` |

> Requiere [Proton Mail Bridge](https://proton.me/mail/bridge) instalado y corriendo

### GMX (`@gmx.com`, `@gmx.es`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.gmx.com` |
| Puerto | `993` |
| SSL | `true` |

> Usa tu contraseña normal. Activa IMAP en: Configuración → POP3 & IMAP

### AOL (`@aol.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.aol.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [login.aol.com/account/security](https://login.aol.com/account/security) → Generate app password

### Yandex (`@yandex.com`, `@ya.ru`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.yandex.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [id.yandex.com/security/app-passwords](https://id.yandex.com/security/app-passwords)

### FastMail (`@fastmail.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.fastmail.com` |
| Puerto | `993` |
| SSL | `true` |

**Contraseña de aplicación:** [fastmail.com/settings/security/devicekeys](https://www.fastmail.com/settings/security/devicekeys)

### Mail.com (`@mail.com`, `@email.com`)

| Campo | Valor |
|-------|-------|
| Servidor | `imap.mail.com` |
| Puerto | `993` |
| SSL | `true` |

> Usa tu contraseña normal. Activa IMAP en: Configuración → POP3 & IMAP

---

## 6. Ejecutar

```bash
# Primera vez (instalar dependencias)
chmod +x start.sh
./start.sh

# O manualmente
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py

# En segundo plano (no se cierra al cerrar terminal)
nohup python3 run.py > /dev/null 2>&1 &

# Con Docker
docker compose up -d
```

## 7. Comandos útiles

```bash
# Ver si está corriendo
ps aux | grep run.py

# Ver logs
tail -f logs/email_monitor.log

# Parar el proceso
kill $(pgrep -f "python3 run.py")

# Resetear (borrar base de datos)
rm -f data/seen_emails.db

# Docker: ver logs / parar
docker compose logs -f
docker compose down
```
