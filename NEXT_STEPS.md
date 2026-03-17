# 🎯 PASOS SIGUIENTES: Sistema listo para Gmail con 2FA

Tu sistema **Inbox Bridge** ahora está completamente configurado para funcionar con cuentas Gmail que tienen **2FA habilitado** sin necesidad de cambiar nada en las cuentas.

## ✅ Lo que ya está hecho

- ✓ 177 cuentas configuradas en `config/accounts.json`
- ✓ Sistema de monitoreo de emails cada 10 segundos
- ✓ Soporte OAuth2 para Gmail 2FA (sin app passwords)
- ✓ Fallback a autenticación por contraseña
- ✓ Documentación completa (SETUP.md, OAUTH2_README.md)
- ✓ Scripts de diagnóstico y setup

## 🚀 PRÓXIMOS PASOS (Elige una opción)

### OPCIÓN A: OAuth2 (⭐ Recomendado - Más seguro)

Funciona sin cambios en las cuentas. Una sola vez:

```bash
# 1. Obtener credenciales de Google (5 minutos)
# Ve a: https://console.cloud.google.com/
# - Crea nuevo proyecto
# - Enable "Gmail API" 
# - Crea OAuth2 credentials (Desktop)
# - Descarga JSON con: client_id y client_secret

# 2. Añade a .env:
GMAIL_CLIENT_ID=tu_client_id
GMAIL_CLIENT_SECRET=tu_client_secret

# 3. Ejecuta el setup interactivo:
./quickstart.sh
# Selecciona opción 2: "Setup Gmail OAuth2"

# 4. Autoriza cuentas en el navegador (una sola vez)
# El sistema abrirá el navegador para cada cuenta Gmail
# Solo haz click en "Allow"

# 5. Inicia el monitor:
python run.py
```

**Ventajas:**
- No requiere app passwords
- No cambia configuración de cuentas
- Tokens se guardan localmente
- Se actualizan automáticamente
- Más seguro

---

### OPCIÓN B: App Passwords (⚡ Más rápido pero requiere cambios)

Si prefieres una solución más rápida:

```bash
# Para CADA cuenta Gmail:
# 1. Ve a: https://myaccount.google.com/apppasswords
# 2. Selecciona "Mail" y "Windows/Linux"
# 3. Genera contraseña de 16 caracteres
# 4. Actualiza config/accounts.json con esa contraseña

# Luego inicia:
python run.py
```

**Nota:** Requiere cambiar 135+ contraseñas manualmente

---

### OPCIÓN C: Contraseña normal sin 2FA

Si deshabilitas 2FA en algunos cuentas:

```bash
# Solo para cuentas Gmail sin 2FA:
# 1. Deshabilita 2FA en: https://myaccount.google.com/security
# 2. Habilita IMAP en: Gmail Settings → Forwarding and POP/IMAP
# 3. Usa tu contraseña normal en config/accounts.json

python run.py
```

---

## 📊 Verificar que funciona

```bash
# Test todas las cuentas:
python test_accounts.py

# Test solo Gmail:
python test_accounts.py gmail

# Test solo Outlook:
python test_accounts.py outlook
```

Mostrará cuáles están funcionando y cuáles tienen problemas.

---

## 📁 Archivos de referencia

Documentación disponible:

- **SETUP.md** - Guía completa en inglés (secciones 1-8)
- **OAUTH2_README.md** - OAuth2 en detalle
- **OAUTH2_QUICK_SETUP.py** - Este archivo ejecutable
- **QUICK_START.md** - Guía rápida en español

---

## 🔐 Seguridad

✅ Protegido:
- `config/accounts.json` - En `.gitignore` (contraseñas seguras)
- `config/.oauth_tokens/` - En `.gitignore` (tokens seguros)
- Seguro hacer: `git push`

---

## 🆘 Troubleshooting

**Error: "IMAP login failed"**
```bash
# Para Gmail con 2FA:
python auth_setup.py

# Para Outlook/otros:
Verifica contraseña en config/accounts.json
```

**Error: "Token expired"**
```bash
python auth_setup.py
# Selecciona: "Re-authenticate specific account"
```

**¿Cuál opción elegir?**
- OAuth2 (Opción A) = ⭐ Recomendado
- App Passwords (Opción B) = Más simple pero menos flexible
- Sin 2FA (Opción C) = Menos seguro

---

## ✨ Resumen rápido

| Aspecto | OAuth2 | App Password | Sin 2FA |
|---------|--------|--------------|---------|
| Seguridad | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| Setup | Una sola vez | Requiere 135+ cambios | 1 cambio |
| Automático | Sí | Sí | Sí |
| Cambios en cuentas | No | No | Sí |
| Recomendado | ✅ | ⚠️ | ❌ |

---

## 🎬 Empezar ahora

```bash
# Opción más fácil (recomendada):
./quickstart.sh

# O directamente:
python run.py
```

¡El sistema está listo! Solo necesitas seguir los pasos de OAuth2 una única vez.

---

**¿Preguntas?** Ver:
- SETUP.md sección 4.1 para OAuth2 detallado
- OAUTH2_README.md para troubleshooting
- test_accounts.py para diagnosticar problemas

