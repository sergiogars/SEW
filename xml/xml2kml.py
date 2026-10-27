#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera etapa.kml a partir de etapaEsquema.xml.

Uso: python xml2kml.py [entrada.xml] [salida.kml]
"""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET


class Xml2Kml:
    NS = {'e': 'http://www.uniovi.es'}
    # KML ordena sus colores así: alfa, azul, verde, rojo.
    COLORES = {'salida_meta': 'ff0000ff', 'puerto': 'ff00ff00',
               'sprint': 'ffff0000', 'localidad': 'ff00ffff'}

    def __init__(self, entrada, salida):
        self.entrada, self.salida = entrada, salida

    def _grados_decimales(self, texto, limite):
        """Convierte -0º 25' 08.18'' a grados decimales para KML."""
        dato = re.fullmatch(r"([+-]?)(\d{1,3})º\s*(\d{1,2})'\s*(\d{1,2}(?:\.\d+)?)''",
                            texto.strip())
        if not dato:
            raise ValueError(f'Coordenada incorrecta: {texto!r}')
        signo, grados, minutos, segundos = dato.groups()
        grados, minutos, segundos = int(grados), int(minutos), float(segundos)
        if grados > limite or minutos >= 60 or segundos >= 60 or (grados == limite and (minutos or segundos)):
            raise ValueError(f'Coordenada fuera de rango: {texto!r}')
        valor = grados + minutos / 60 + segundos / 3600
        return -valor if signo == '-' else valor

    def _punto(self, nodo, nombre, tipo, km):
        lon = nodo.findtext('./e:coordenadas/e:longitud', namespaces=self.NS)
        lat = nodo.findtext('./e:coordenadas/e:latitud', namespaces=self.NS)
        alt = nodo.findtext('./e:coordenadas/e:altitud', namespaces=self.NS)
        if not all((lon, lat, alt)):
            raise ValueError(f'Faltan coordenadas de {nombre}')
        coordenadas = (f'{self._grados_decimales(lon, 180):.8f},'
                       f'{self._grados_decimales(lat, 90):.8f},{float(alt):g}')
        return {'nombre': nombre, 'tipo': tipo, 'km': float(km),
                'coordenadas': coordenadas}

    def generar(self):
        raiz = ET.parse(self.entrada).getroot()
        if raiz.tag != '{http://www.uniovi.es}etapa':
            raise ValueError('El XML debe tener el espacio de nombres http://www.uniovi.es')
        longitud = float(raiz.findtext('e:longitud_etapa', namespaces=self.NS))
        puntos = []
        salida = raiz.find('e:salida', self.NS)
        llegada = raiz.find('e:llegada', self.NS)
        puntos.append(self._punto(salida, 'Salida: ' + salida.findtext('e:lugar', namespaces=self.NS),
                                  'salida_meta', 0))
        for hito in raiz.findall('e:hitos/*', self.NS):  # XPath
            tipo = 'puerto' if hito.tag.endswith('}puerto') else 'sprint'
            nombre = hito.findtext('e:nombre', default='Sprint intermedio', namespaces=self.NS)
            km = hito.findtext('e:distancia', namespaces=self.NS)
            puntos.append(self._punto(hito, nombre, tipo, km))
        localidades = raiz.findall('e:puntos_anonimos/e:punto', self.NS)  # XPath
        if len(localidades) > 30:
            raise ValueError('El guion limita los puntos anónimos a 30')
        for indice, nodo in enumerate(localidades, 1):
            nombre = nodo.get('nombre') or f'Punto {indice}'
            puntos.append(self._punto(nodo, nombre, 'localidad',
                                      nodo.findtext('e:distancia', namespaces=self.NS)))
        puntos.append(self._punto(llegada, 'Meta: ' + llegada.findtext('e:lugar', namespaces=self.NS),
                                  'salida_meta', longitud))
        puntos.sort(key=lambda punto: punto['km'])

        kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
        documento = ET.SubElement(kml, 'Document')
        numero = raiz.findtext('e:numero', namespaces=self.NS)
        nombre = raiz.findtext('e:nombre', namespaces=self.NS)
        ET.SubElement(documento, 'name').text = f'Etapa {numero}: {nombre}'
        for tipo, color in self.COLORES.items():
            estilo = ET.SubElement(documento, 'Style', id=tipo)
            icono = ET.SubElement(estilo, 'IconStyle')
            ET.SubElement(icono, 'color').text = color
            ET.SubElement(ET.SubElement(icono, 'Icon'), 'href').text = (
                'http://maps.google.com/mapfiles/kml/paddle/wht-blank.png')
        estilo = ET.SubElement(documento, 'Style', id='recorrido')
        linea_estilo = ET.SubElement(estilo, 'LineStyle')
        ET.SubElement(linea_estilo, 'color').text = 'ff00a5ff'
        ET.SubElement(linea_estilo, 'width').text = '4'
        for tipo, titulo in [('salida_meta', 'Salida y meta'), ('puerto', 'Puertos'),
                             ('sprint', 'Sprint intermedio'), ('localidad', 'Localidades')]:
            carpeta = ET.SubElement(documento, 'Folder')
            ET.SubElement(carpeta, 'name').text = titulo
            for punto in (p for p in puntos if p['tipo'] == tipo):
                marca = ET.SubElement(carpeta, 'Placemark')
                ET.SubElement(marca, 'name').text = punto['nombre']
                ET.SubElement(marca, 'description').text = f"Km {punto['km']:g}"
                ET.SubElement(marca, 'styleUrl').text = '#' + tipo
                geometria = ET.SubElement(marca, 'Point')
                ET.SubElement(geometria, 'altitudeMode').text = 'clampToGround'
                ET.SubElement(geometria, 'coordinates').text = punto['coordenadas']
        marca = ET.SubElement(documento, 'Placemark')
        ET.SubElement(marca, 'name').text = 'Recorrido aproximado'
        ET.SubElement(marca, 'styleUrl').text = '#recorrido'
        linea = ET.SubElement(marca, 'LineString')
        ET.SubElement(linea, 'tessellate').text = '1'
        ET.SubElement(linea, 'altitudeMode').text = 'clampToGround'
        ET.SubElement(linea, 'coordinates').text = '\n'.join(p['coordenadas'] for p in puntos)
        arbol = ET.ElementTree(kml)
        ET.indent(arbol)
        arbol.write(self.salida, encoding='utf-8', xml_declaration=True)
        print(f'Creado {self.salida}: {len(puntos)} puntos.')

    @classmethod
    def main(cls):
        carpeta = Path(__file__).resolve().parent
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('entrada', nargs='?', type=Path, default=carpeta / 'etapaEsquema.xml')
        parser.add_argument('salida', nargs='?', type=Path, default=carpeta / 'etapa.kml')
        args = parser.parse_args()
        cls(args.entrada, args.salida).generar()


if __name__ == '__main__':
    Xml2Kml.main()
