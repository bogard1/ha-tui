# HA-TUI - Home Assistant Terminal Dashboard

Un dashboard de terminal para Home Assistant construido con Textual, que proporciona monitoreo y control en tiempo real de tus entidades de Home Assistant.

## Características

- 🔄 **Tiempo real**: Conexión WebSocket para actualizaciones instantáneas
- 📊 **Widgets variados**: Valores, estados binarios, gráficos sparkline y botones de acción
- 📱 **Multi-página**: Navega entre diferentes vistas de tu dashboard
- ⚙️ **Configurable**: YAML simple para personalizar completamente tu dashboard
- 🔧 **Debug**: Herramientas incluidas para verificar conectividad

## Instalación

Requiere Python 3.7+ y las siguientes dependencias:

```bash
# Instalar dependencias
pip install -r requirements.txt

# O instalar manualmente:
pip install aiohttp websockets textual pyyaml python-dotenv
```

## Configuración

### 1. Crear archivo de configuración

Copia `dashboard.yml.example` a `dashboard.yml` o crea tu propio archivo:

```yaml
ha:
  url: "http://192.168.1.100:8123"
  token: "${HA_TOKEN}"  # Variable de entorno recomendada
  verify_ssl: false

ui:
  refresh_ms: 250
  theme: "auto"

pages:
  - id: "home"
    title: "Casa"
    layout: "grid-2"
    widgets:
      - type: "value"
        entity: "sensor.temperature_living"
        label: "Temperatura"
        unit: "°C"
        fmt: ".1f"
```

### 2. Token de Home Assistant

Genera un token de larga duración en Home Assistant:
1. Ve a **Perfil** → **Tokens de acceso de larga duración**
2. Crea un nuevo token
3. Configúralo usando una de estas opciones:

#### Opción A: Archivo .env (Recomendado)
```bash
# Copia el archivo de ejemplo
cp .env.example .env

# Edita .env y agrega tu token:
HA_TOKEN=tu_token_de_home_assistant_aqui
```

#### Opción B: Variable de entorno
```bash
export HA_TOKEN="tu_token_aqui"
```

## Uso

### Ejecutar dashboard

```bash
# Usar dashboard.yml por defecto
python ha-tui.py

# Usar archivo personalizado
python ha-tui.py dashboard-temps.yml
```

### Navegación

- **Tab**: Página siguiente
- **Shift+Tab**: Página anterior
- **R**: Recargar configuración
- **Q**: Salir

### Debug de conexión

```bash
python debug-ha.py
```

## Tipos de Widgets

### Value Widget
Muestra valores numéricos de sensores:

```yaml
- type: "value"
  entity: "sensor.temperature"
  label: "Temperatura"
  unit: "°C"
  fmt: ".1f"  # Formato numérico
```

### Binary Widget
Estados binarios (on/off, open/closed):

```yaml
- type: "binary"
  entity: "light.living_room"
  label: "Luz Living"
  on_text: "ENCENDIDA"
  off_text: "APAGADA"
```

### Sparkline Widget
Gráficos ASCII de historial:

```yaml
- type: "sparkline"
  entity: "sensor.temperature"
  label: "Temp (1h)"
  window: 60  # Número de muestras
```

### Action Widget
Botones para ejecutar servicios:

```yaml
- type: "action"
  label: "Toggle Luz"
  service: "light/toggle"
  data:
    entity_id: "light.living_room"
```

## Layouts

- **`rows`**: Widgets apilados verticalmente
- **`grid-1`**: Una columna
- **`grid-2`**: Dos columnas
- **`grid-3`**: Tres columnas

## Configuración Avanzada

### Keybinds personalizados

```yaml
keybinds:
  next_page: "tab"
  prev_page: "shift+tab"
  reload_config: "r"
  quit: "q"
```

### SSL y conexiones seguras

```yaml
ha:
  url: "https://tu-ha.com"
  token: "${HA_TOKEN}"
  verify_ssl: true  # Para certificados válidos
```

## Estructura del Proyecto

```
ha-tui/
├── ha-tui.py              # Aplicación principal
├── debug-ha.py            # Debug de conexión
├── requirements.txt       # Dependencias Python
├── .env.example          # Plantilla para variables de entorno
├── dashboard.yml          # Configuración principal
├── dashboard-temps.yml    # Ejemplo: solo temperaturas
├── CLAUDE.md             # Documentación técnica para Claude Code
└── README.md             # Esta documentación
```

## Cómo Funciona el Código

### Arquitectura General

El script `ha-tui.py` está estructurado en cuatro componentes principales que trabajan juntos para crear una interfaz de terminal reactiva:

#### 1. Carga de Entorno (líneas 4, 11)
**Función**: Carga automática de variables de entorno desde archivo .env
- Usa `python-dotenv` para cargar variables al inicio
- Soporte para archivos `.env` y variables de sistema

#### 2. HAClient (líneas 19-107)
**Función**: Gestiona toda la comunicación con Home Assistant

**Componentes clave**:
- **WebSocket Connection**: Establece conexión persistente para recibir eventos en tiempo real
- **State Cache**: Mantiene un diccionario `{entity_id: state_dict}` con el estado actual de todas las entidades
- **History Buffer**: Almacena hasta 600 muestras históricas por entidad para generar gráficos sparkline
- **Service Calls**: Permite ejecutar servicios de Home Assistant (toggle, turn_on, etc.)

**Flujo de conexión**:
1. Conecta via WebSocket (`connect_ws()`)
2. Realiza autenticación con token
3. Se suscribe a eventos `state_changed`
4. Obtiene estados iniciales via REST API
5. Escucha eventos continuamente (`pump()`)

#### 3. Sistema de Widgets (líneas 110-182)
**Función**: Componentes visuales reactivos que muestran datos de HA

**Tipos implementados**:

- **ValueWidget**: Muestra valores numéricos con formato personalizable
  ```python
  # Renderiza: "Temperatura\n23.5°C"
  val = format(float(state), self.fmt)  # Aplica formato numérico
  ```

- **BinaryWidget**: Estados on/off con texto personalizable
  ```python
  # Lógica: on/open/detected = texto_encendido, resto = texto_apagado
  text = self.on_text if state in ("on", "open", "detected") else self.off_text
  ```

- **SparklineWidget**: Gráficos ASCII de tendencias históricas
  ```python
  # Algoritmo: normaliza datos al rango de caracteres ▁▂▃▄▅▆▇█
  blocks = "▁▂▃▄▅▆▇█"
  normalized_value = int((value - min_val) / range * 7)
  ```

- **ActionWidget**: Botones clickeables que ejecutan servicios HA
  ```python
  # Al hacer click: llama ha.call_service(service, data)
  await self.ha.call_service("light/toggle", {"entity_id": "light.living"})
  ```

#### 4. HADashboard App (líneas 184-305)
**Función**: Aplicación principal de Textual que orquesta la UI

**Ciclo de vida**:
1. **Inicialización**: Carga configuración y configura keybinds
2. **Mount**: Establece conexión HA, monta interfaz, inicia workers
3. **Runtime**: Refresca UI periódicamente, maneja navegación
4. **Unmount**: Cierra conexiones al salir

**Sistema de páginas**:
- Cada página define layout (grid-1/2/3, rows) y lista de widgets
- Navegación circular entre páginas con Tab/Shift+Tab
- Reconstrucción dinámica de widgets al cambiar página

#### 5. Gestión de Estado Reactivo

**Patrón Publisher-Subscriber**:
```python
# HAClient recibe eventos WebSocket
state_cache[entity_id] = new_state  # Actualiza cache

# Widgets acceden al cache compartido
state = self.state_cache.get(self.entity)  # Lee estado actual

# UI se refresca periódicamente
self.set_interval(refresh_ms/1000.0, self.refresh)  # Trigger re-render
```

**Flujo de datos**:
```
Home Assistant → WebSocket → HAClient.state_cache → Widgets → Textual UI
                    ↓
                History Buffer → SparklineWidget
```

### Detalles Técnicos Importantes

#### Manejo de Conexiones
- **SSL flexible**: Soporte para certificados auto-firmados con `verify_ssl: false`
- **Reconexión**: WebSocket se mantiene abierto; la app maneja desconexiones automáticamente
- **Async/await**: Todo I/O es asíncrono para evitar bloqueos de UI

#### Optimizaciones de Performance
- **Cache de estados**: Evita consultas REST repetitivas
- **History limitado**: Buffer circular de 600 muestras máximo por entidad
- **Refresh configurable**: UI actualiza solo cuando es necesario (default: 250ms)
- **Workers exclusivos**: Un solo worker para eventos WebSocket evita condiciones de carrera

#### Gestión de Errores
- **Valores no numéricos**: ValueWidget muestra "Error: valor" en lugar de crash
- **Entidades faltantes**: Widgets muestran "—" cuando entidad no existe
- **Servicios fallidos**: ActionWidget muestra mensaje de error específico

#### Configuración Dinámica
- **Variables de entorno**: Soporte para `${VAR}` en YAML
- **Reload en caliente**: Tecla 'R' recarga configuración sin reiniciar app
- **Keybinds personalizables**: Mapeo flexible de teclas en YAML

Este diseño modular permite fácil extensión de nuevos tipos de widgets y mantiene separación clara entre lógica de datos (HAClient) y presentación (Widgets/App).

## Troubleshooting

### Error de conexión
1. Ejecuta `python debug-ha.py` para verificar conectividad
2. Verifica URL y token en tu configuración
3. Revisa que Home Assistant esté accesible

### SSL/HTTPS
- Para certificados auto-firmados: `verify_ssl: false`
- Para conexiones locales HTTP: usar `http://` en la URL

### Entidades no encontradas
- Verifica nombres de entidades en Home Assistant
- Usa el debug script para listar entidades disponibles

## Contribuir

1. Fork el proyecto
2. Crea tu feature branch
3. Commit tus cambios
4. Push al branch
5. Abre un Pull Request

## Licencia

MIT License - ve el archivo LICENSE para detalles.