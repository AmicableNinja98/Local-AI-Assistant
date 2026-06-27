-- Estructura de Base de Datos para el Asistente de IA Local
CREATE DATABASE IF NOT EXISTS asistente_ia;
USE asistente_ia;

CREATE TABLE IF NOT EXISTS usuario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(50) UNIQUE,
    valor VARCHAR(255)
);

INSERT IGNORE INTO usuario (clave, valor) VALUES ('nombre_usuario', 'AmicableNinja98');

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
