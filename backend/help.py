def ayuda_asistente():
    return """
====================================================================
📋 FUNCIONES DISPONIBLES
====================================================================
1. 💬 Conversación libre en español o inglés.
2. 🔍 Búsqueda web automática para información reciente.
   También puedes forzarla con '/buscar [consulta]'.
3. 👤 Recuerdo tu nombre gracias a MariaDB.
4. 🖥️  Abrir aplicaciones: 'Abre Steam', 'Abre Discord', etc.
   Si no conozco la ruta te la pediré y la recordaré para siempre.
5. ⚽ GESTIÓN DEPORTIVA:
   · Torneos: crear, inscribir equipos
   · Sorteo: 'Realiza el sorteo de grupos de [torneo]'
             Adapta automáticamente según el nº de equipos
             Formatos: 4, 6, 8, 12, 16, 24, 32, 48 equipos
   · Grupos: crear grupos (A, B...), añadir equipos a grupos
   · Partidos: programar fixtures, registrar resultados
   · Tabla: ver clasificación general o por grupo
   · Eliminatorias: 'Genera las eliminatorias de [torneo]'
                    Cruces automáticos (1ºA vs 2ºB...)
   · Jugadores: registrar goles, asistencias, tarjetas
   · Stats: ver tabla de goleadores y estadísticas
6. ❓ Ayuda: escribe '/ayuda' o pregúntame qué puedo hacer.
7. 🖥️ Compartir archivos con otros dispositivos de tu red local.
====================================================================
Ejemplo de flujo Copa del Mundo:
  'Crea el torneo "World Cup 2026"'
  'Crea el equipo España'
  'Inscribe España en "World Cup 2026"'
  'Realiza el sorteo de grupos de "World Cup 2026"'
  'Registra el resultado: España 2 - Alemania 1 en "World Cup 2026"'
  'Muestra la clasificación del Grupo A de "World Cup 2026"'
  'Genera las eliminatorias de "World Cup 2026"'
  'Ver cuadro de "World Cup 2026"'
===================================================================="""
