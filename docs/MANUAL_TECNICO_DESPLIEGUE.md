# Manual Técnico y de Despliegue — Electorry SpA

Este documento describe la arquitectura del sistema, los requisitos técnicos, y el procedimiento paso a paso para el despliegue local, en Staging y en Producción (Render).

## 1. Arquitectura del Sistema
El proyecto está construido bajo un patrón de **monolito modular** utilizando **Django 5**. El stack está contenerizado con **Docker** para garantizar la paridad entre entornos.
- **Servidor Web:** Nginx (Proxy inverso y archivos estáticos).
- **Servidor de Aplicación:** Gunicorn.
- **Base de Datos:** PostgreSQL 16.
- **Servicios Externos:** Pasarelas de pago (Webpay, Mercado Pago) y servidor SMTP para correos.

## 2. Requisitos Previos
- Python 3.12+
- PostgreSQL 16 (o Docker Desktop)
- Git
- Cuenta en Render (para producción)

## 3. Instalación Local (Desarrollo)
1. Clonar el repositorio:
   ```bash
   git clone https://github.com/YamikugoKurogane/Electorry-SpA-Plataforma-Web-de-Servicios-y-E-commerce.git
   cd Electorry-SpA-Plataforma-Web-de-Servicios-y-E-commerce