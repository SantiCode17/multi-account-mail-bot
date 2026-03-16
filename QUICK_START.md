# 🚀 CÓMO INICIAR EL BOT AUTOMÁTICAMENTE

## Resumen rápido (3 pasos)

```bash
# 1. Configurar (primera vez)
./start.sh

# 2. Instalar como servicio (una sola vez)
sudo deployment/install-service.sh

# ¡LISTO! El bot se inicia automáticamente al encender el ordenador
```

---

## PASO 1: Configuración Inicial (Primera vez)

### 1a. Crear el archivo `.env`

En la carpeta del proyecto, crea un archivo llamado `.env` con este contenido:

```env
TELEGRAM_BOT_TOKEN=aqui_tu_token_de_botfather
TELEGRAM_CHAT_ID=aqui_tu_chat_id
CHECK_INTERVAL_SECONDS=10
MAX_CONCURRENT_CONNECTIONS=20
BATCH_SIZE=50
EMAIL_BODY_PREVIEW_LENGTH=500
DATABASE_PATH=data/seen_emails.db
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/email_monitor.log
ACCOUNTS_CONFIG_PATH=config/accounts.json
```

¿Dónde consigo el token y el chat ID?
→ Ver secciones 1-2 de `SETUP.md`

### 1b. Configurar cuentas de correo

Edita el archivo `config/accounts.json`:

```json
{
  "accounts": [
    {
      "email": "tu_correo@gmail.com",
      "password": "tu_contraseña_de_aplicacion",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

¿Cómo consigo la contraseña de aplicación?
→ Ver sección 5 de `SETUP.md` (hay 11 proveedores listados)

### 1c. Ejecutar el script de inicio

```bash
chmod +x start.sh
./start.sh
```

Esto:
- Verifica que tengas Python 3.10+
- Crea un "entorno virtual" (caja aislada para la app)
- Instala las dependencias
- Valida que todo esté configurado correctamente
- **IMPORTANTE**: Esto **NO lo instala como servicio**, solo lo prueba una vez

---

## PASO 2: Instalar como Servicio Automático (Una sola vez)

Una vez hayas comprobado que funciona, instálalo como **servicio del sistema**:

```bash
sudo deployment/install-service.sh
```

Este script:
1. Verifica que todo esté bien configurado
2. Crea un archivo de servicio en `/etc/systemd/system/`
3. Lo configura para que se inicie automáticamente al boot
4. Lo inicia inmediatamente

---

## PASO 3: ¿Listo! El bot está activo permanentemente

Una vez instalado como servicio:

✅ Se inicia **automáticamente al encender el ordenador**
✅ Se reinicia solo si **se cuelga o falla**
✅ Corre **en segundo plano** sin ventana abierta
✅ Puedes **cerrar el terminal** sin que se detenga

---

## COMANDOS PARA GESTIONAR EL SERVICIO

Una vez instalado como servicio, usa estos comandos:

### Ver el estado actual

```bash
systemctl status inbox-bridge-$USER.service
```

**Salida esperada:**
```
● inbox-bridge-santiago.service - Inbox Bridge — Email Monitor Bot Service
   Loaded: loaded (/etc/systemd/system/inbox-bridge-santiago.service; enabled; vendor preset: enabled)
   Active: active (running) since [fecha y hora]
   ...
```

### Ver los logs en **TIEMPO REAL**

```bash
journalctl -u inbox-bridge-$USER.service -f
```

Presiona `Ctrl+C` para salir.

### Detener el servicio

```bash
systemctl stop inbox-bridge-$USER.service
```

Después puedes reiniciarlo con:

```bash
systemctl start inbox-bridge-$USER.service
```

### Reiniciar el servicio

```bash
systemctl restart inbox-bridge-$USER.service
```

### Desinstalar el servicio (para volver atrás)

```bash
sudo systemctl disable inbox-bridge-$USER.service
sudo rm /etc/systemd/system/inbox-bridge-$USER.service
sudo systemctl daemon-reload
```

---

## FLUJO COMPLETO DESDE CERO

Si estás empezando de cero, esto es lo que debes hacer:

### Día 1: Setup

```bash
# 1. Descarga el proyecto desde GitHub
git clone https://github.com/SantiCode17/multi-account-mail-bot.git
cd multi-account-mail-bot

# 2. Crea el archivo .env con tus tokens
nano .env
# (Pega el contenido del ejemplo arriba, reemplaza tokens)

# 3. Configura tus cuentas de correo
nano config/accounts.json
# (Sigue las instrucciones de SETUP.md sección 5)

# 4. Prueba que funciona
chmod +x start.sh
./start.sh
# (Si ves "✔ Configuration valid" y no hay errores, está bien)
# Presiona Ctrl+C para detenerlo

# 5. Instálalo como servicio permanente
sudo deployment/install-service.sh

# ¡LISTO!
```

### Día 2 en adelante

El bot está **AUTOMÁTICAMENTE activo**. Solo necesitas:

```bash
# Ver si sigue corriendo
systemctl status inbox-bridge-$USER.service

# Ver logs si hay problemas
journalctl -u inbox-bridge-$USER.service -f

# Si necesitas agregar una cuenta de correo nueva:
# 1. Edita config/accounts.json
# 2. Reinicia el servicio:
systemctl restart inbox-bridge-$USER.service
```

---

## SOLUCIÓN DE PROBLEMAS

### "El servicio no inicia"

Primero, comprueba que `.env` está bien:

```bash
cat .env | grep TELEGRAM_BOT_TOKEN
cat .env | grep TELEGRAM_CHAT_ID
```

Si ves `your_bot_token_here` o `your_chat_id_here`, **aún no has puesto tus datos reales**.

### "¿Cómo sé si está funcionando?"

```bash
# Opción 1: Ver estado
systemctl status inbox-bridge-$USER.service

# Opción 2: Ver si el proceso Python está corriendo
ps aux | grep run.py

# Opción 3: Ver logs
journalctl -u inbox-bridge-$USER.service -n 20
```

### "Recibo un error de 'sudo': command not found"

Significa que `sudo` no está instalado en tu sistema. En lugar de:
```bash
sudo deployment/install-service.sh
```

Sé root y luego ejecuta:
```bash
su -
deployment/install-service.sh
```

### "¿Qué significa 'systemctl'?"

Es el programa que gestiona los servicios en Linux. Es como un "gerente" que:
- Inicia/detiene programas
- Los hace ejecutarse al boot
- Los reinicia si fallan
- Guarda logs

---

## DIFERENCIA ENTRE MÉTODOS

| Método | Cómo | Ventajas | Desventajas |
|--------|------|----------|------------|
| **`./start.sh`** | Manual cada vez | Rápido de probar | Se detiene al cerrar terminal |
| **`nohup python3 run.py &`** | Manual pero en background | Sobrevive terminal cerrado | Hay que escribir comandos largos |
| **`systemctl` (Servicio)** | Automático al boot | Siempre activo, restarts automáticos | Requiere `sudo` una sola vez |
| **Docker** | `docker compose up -d` | Super portable | Más complejo de entender |

---

## ¿NECESITAS MÁS AYUDA?

1. **¿Cómo creo el token de Telegram?** → Ver `SETUP.md` sección 1
2. **¿Cómo obtengo mi Chat ID?** → Ver `SETUP.md` sección 2
3. **¿Cómo configuró Gmail, Outlook, Yahoo?** → Ver `SETUP.md` sección 5
4. **¿Qué hace cada línea del .env?** → Ver `SETUP.md` sección 3

