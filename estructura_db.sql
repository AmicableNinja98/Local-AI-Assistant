-- Estructura de Base de Datos para el Asistente de IA Local
CREATE DATABASE IF NOT EXISTS asistente_ia;
USE asistente_ia;

CREATE TABLE IF NOT EXISTS usuario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(50) UNIQUE,
    valor VARCHAR(255)
);

INSERT IGNORE INTO usuario (clave, valor) VALUES ('nombre_usuario', 'AmicableNinja98');
INSERT IGNORE INTO usuario (clave,valor) VALUES ('nombre_asistente','Alfred')

CREATE TABLE IF NOT EXISTS jugadores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    edad INT,
    posicion VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS equipos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS torneos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    fecha_inicio DATE,
    estado VARCHAR(50) DEFAULT 'Planificado'
);

CREATE TABLE IF NOT EXISTS equipo_jugadores (
    equipo_id INT,
    jugador_id INT,
    PRIMARY KEY (equipo_id, jugador_id),
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE,
    FOREIGN KEY (jugador_id) REFERENCES jugadores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS torneo_equipos (
    torneo_id INT,
    equipo_id INT,
    PRIMARY KEY (torneo_id, equipo_id),
    FOREIGN KEY (torneo_id) REFERENCES torneos(id) ON DELETE CASCADE,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

-- Groups within a tournament (Group A, B, C...)
CREATE TABLE IF NOT EXISTS grupos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    torneo_id INT NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    FOREIGN KEY (torneo_id) REFERENCES torneos(id) ON DELETE CASCADE,
    UNIQUE (torneo_id, nombre)
);

-- Teams assigned to a group
CREATE TABLE IF NOT EXISTS grupo_equipos (
    grupo_id INT NOT NULL,
    equipo_id INT NOT NULL,
    PRIMARY KEY (grupo_id, equipo_id),
    FOREIGN KEY (grupo_id) REFERENCES grupos(id) ON DELETE CASCADE,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

-- Matches (scheduled or played)
CREATE TABLE IF NOT EXISTS partidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    torneo_id INT NOT NULL,
    equipo_local_id INT NOT NULL,
    equipo_visitante_id INT NOT NULL,
    goles_local INT DEFAULT NULL,
    goles_visitante INT DEFAULT NULL,
    fecha DATE DEFAULT NULL,
    fase VARCHAR(50) DEFAULT 'Fase de grupos',
    grupo_id INT DEFAULT NULL,
    estado VARCHAR(20) DEFAULT 'programado',
    FOREIGN KEY (torneo_id) REFERENCES torneos(id) ON DELETE CASCADE,
    FOREIGN KEY (equipo_local_id) REFERENCES equipos(id),
    FOREIGN KEY (equipo_visitante_id) REFERENCES equipos(id),
    FOREIGN KEY (grupo_id) REFERENCES grupos(id)
);

-- Team stats per tournament (auto-updated when result is registered)
CREATE TABLE IF NOT EXISTS estadisticas_equipo_torneo (
    torneo_id INT NOT NULL,
    equipo_id INT NOT NULL,
    partidos_jugados INT DEFAULT 0,
    victorias INT DEFAULT 0,
    empates INT DEFAULT 0,
    derrotas INT DEFAULT 0,
    goles_favor INT DEFAULT 0,
    goles_contra INT DEFAULT 0,
    puntos INT DEFAULT 0,
    PRIMARY KEY (torneo_id, equipo_id),
    FOREIGN KEY (torneo_id) REFERENCES torneos(id) ON DELETE CASCADE,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id) ON DELETE CASCADE
);

-- Player stats per tournament
CREATE TABLE IF NOT EXISTS estadisticas_jugador_torneo (
    torneo_id INT NOT NULL,
    jugador_id INT NOT NULL,
    equipo_id INT DEFAULT NULL,
    partidos_jugados INT DEFAULT 0,
    goles INT DEFAULT 0,
    asistencias INT DEFAULT 0,
    tarjetas_amarillas INT DEFAULT 0,
    tarjetas_rojas INT DEFAULT 0,
    PRIMARY KEY (torneo_id, jugador_id),
    FOREIGN KEY (torneo_id) REFERENCES torneos(id) ON DELETE CASCADE,
    FOREIGN KEY (jugador_id) REFERENCES jugadores(id) ON DELETE CASCADE,
    FOREIGN KEY (equipo_id) REFERENCES equipos(id)
);

CREATE TABLE IF NOT EXISTS aplicaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    ruta VARCHAR(500) NOT NULL
);