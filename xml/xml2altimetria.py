#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera altimetria.svg a partir de etapaEsquema.xml.

Uso: python xml2altimetria.py [entrada.xml] [salida.svg]
"""
import argparse
from math import ceil
from pathlib import Path
import xml.etree.ElementTree as ET


class Xml2Altimetria:
    NS = {'e': 'http://www.uniovi.es'}

    def __init__(self, entrada, salida):
        self.entrada, self.salida = entrada, salida

    def _punto(self, nodo, km, nombre, tipo):
        altitud = nodo.findtext('e:coordenadas/e:altitud', namespaces=self.NS)
        if altitud is None:
            raise ValueError(f'Falta la altitud de {nombre}')
        return (float(km), float(altitud), nombre, tipo)

    def generar(self):
        raiz = ET.parse(self.entrada).getroot()
        if raiz.tag != '{http://www.uniovi.es}etapa':
            raise ValueError('El XML debe tener el espacio de nombres http://www.uniovi.es')
        longitud = float(raiz.findtext('e:longitud_etapa', namespaces=self.NS))
        salida = raiz.find('e:salida', self.NS)
        llegada = raiz.find('e:llegada', self.NS)
        puntos = [self._punto(salida, 0, salida.findtext('e:lugar', namespaces=self.NS), 'salida')]
        for hito in raiz.findall('e:hitos/*', self.NS):  # XPath
            tipo = 'puerto' if hito.tag.endswith('}puerto') else 'sprint'
            puntos.append(self._punto(hito, hito.findtext('e:distancia', namespaces=self.NS),
                                      hito.findtext('e:nombre', namespaces=self.NS) or 'Sprint', tipo))
        localidades = raiz.findall('e:puntos_anonimos/e:punto', self.NS)  # XPath
        if len(localidades) > 30:
            raise ValueError('El guion limita los puntos anónimos a 30')
        for indice, nodo in enumerate(localidades, 1):
            puntos.append(self._punto(nodo, nodo.findtext('e:distancia', namespaces=self.NS),
                                      nodo.get('nombre') or f'Punto {indice}', 'localidad'))
        puntos.append(self._punto(llegada, longitud,
                                  llegada.findtext('e:lugar', namespaces=self.NS), 'meta'))
        puntos.sort(key=lambda p: p[0])

        # Versión de tu xml2perfil.py: los km y las altitudes se escalan al SVG.
        ancho, alto = 1280, 740
        izq, der, arriba, abajo = 85, 1225, 205, 560
        techo = max(250, ceil(max(p[1] for p in puntos) / 250) * 250)
        escala_x = (der - izq) / longitud
        escala_y = (abajo - arriba) / techo
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        svg = ET.Element('{http://www.w3.org/2000/svg}svg',
                         width=str(ancho), height=str(alto), viewBox=f'0 0 {ancho} {alto}')
        ns = '{http://www.w3.org/2000/svg}'
        nombre_etapa = raiz.findtext('e:nombre', namespaces=self.NS)
        numero = raiz.findtext('e:numero', namespaces=self.NS)
        ET.SubElement(svg, ns + 'title').text = f'Altimetría de la etapa {numero}'
        ET.SubElement(svg, ns + 'rect', width=str(ancho), height=str(alto), fill='white')
        ET.SubElement(svg, ns + 'text', x=str(izq), y='48', fill='#253b4e',
                      attrib={'font-size': '29', 'font-weight': 'bold'}).text = 'ALTIMETRÍA'
        ET.SubElement(svg, ns + 'text', x=str(izq), y='77', fill='#42586c',
                      attrib={'font-size': '17'}).text = f'Etapa {numero} · {nombre_etapa}'
        ET.SubElement(svg, ns + 'text', x=str(der), y='50', fill='#c64737',
                      attrib={'text-anchor': 'end', 'font-size': '21'}).text = f'{longitud:g} km'
        for alt in range(0, techo + 1, 250):
            y = abajo - alt * escala_y
            ET.SubElement(svg, ns + 'line', x1=str(izq), y1=f'{y:.1f}', x2=str(der),
                          y2=f'{y:.1f}', stroke='#dde5eb')
            ET.SubElement(svg, ns + 'text', x=str(izq - 12), y=f'{y + 4:.1f}',
                          fill='#607487', attrib={'font-size': '11',
                                                  'text-anchor': 'end'}).text = str(alt)
        for km in range(0, int(longitud), 25):
            x = izq + km * escala_x
            ET.SubElement(svg, ns + 'line', x1=f'{x:.1f}', y1=str(arriba),
                          x2=f'{x:.1f}', y2=str(abajo), stroke='#edf1f4')
            ET.SubElement(svg, ns + 'text', x=f'{x:.1f}', y=str(abajo + 23),
                          fill='#607487', attrib={'text-anchor': 'middle',
                                                  'font-size': '11'}).text = str(km)
        ET.SubElement(svg, ns + 'text', x=str(der), y=str(abajo + 23),
                      fill='#607487', attrib={'text-anchor': 'middle',
                                              'font-size': '11'}).text = f'{longitud:g}'
        ET.SubElement(svg, ns + 'text', x=str(izq), y=str(arriba - 12),
                      fill='#607487', attrib={'font-size': '12'}).text = 'Altitud (m)'
        ET.SubElement(svg, ns + 'text', x=str(der), y=str(abajo + 48),
                      fill='#607487', attrib={'text-anchor': 'end',
                                              'font-size': '12'}).text = 'Distancia (km)'

        vertices = [f'{izq + km * escala_x:.1f},{abajo - alt * escala_y:.1f}'
                    for km, alt, _, _ in puntos]
        ET.SubElement(svg, ns + 'polyline',
                      points=' '.join(vertices + [f'{der},{abajo}', f'{izq},{abajo}']),
                      fill='#f3b39e', stroke='none', attrib={'fill-opacity': '0.7'})
        ET.SubElement(svg, ns + 'polyline', points=' '.join(vertices),
                      fill='none', stroke='#c64737', attrib={'stroke-width': '3'})
        colores = {'salida': '#16a5bd', 'meta': '#d74736', 'puerto': '#984bab',
                   'sprint': '#b98d00', 'localidad': '#318568'}
        cortos = {'Puerto El Remolcador': 'Remolcador',
                  'Alto de Zucaina': 'Zucaina',
                  'Puerto de Fuente de Rubielos': 'Fuente Rubielos',
                  'Puerto de San Rafael': 'San Rafael'}
        for km, alt, nombre, tipo in puntos:
            x, y = izq + km * escala_x, abajo - alt * escala_y
            marca = ET.SubElement(svg, ns + 'g')
            ET.SubElement(marca, ns + 'title').text = f'{nombre}: km {km:g}, {alt:g} m'
            ET.SubElement(marca, ns + 'circle', cx=f'{x:.1f}', cy=f'{y:.1f}',
                          r='5' if tipo != 'localidad' else '3', fill=colores[tipo])
            if tipo != 'localidad':
                etiqueta = {'salida': 'SALIDA', 'meta': 'META',
                            'sprint': 'SPRINT'}.get(tipo, cortos.get(nombre, nombre))
                ET.SubElement(svg, ns + 'text', x=f'{x-5:.1f}', y='190',
                              fill=colores[tipo], attrib={'font-size': '12',
                              'font-weight': 'bold',
                              'transform': f'rotate(-90 {x-5:.1f} 190)'}).text = etiqueta
                ET.SubElement(svg, ns + 'text', x=f'{x-8 if tipo == "meta" else x+8:.1f}',
                              y=f'{y-10:.1f}', fill=colores[tipo],
                              attrib={'font-size': '11',
                              'text-anchor': 'end' if tipo == 'meta' else 'start'}).text = f'{alt:g} m'
        ET.SubElement(svg, ns + 'text', x=str(izq), y='680', fill='#607487',
                      attrib={'font-size': '12'}).text = (
                          'Perfil aproximado: los puntos del XML se unen mediante segmentos rectos.')
        arbol = ET.ElementTree(svg)
        ET.indent(arbol)
        arbol.write(self.salida, encoding='utf-8', xml_declaration=True)
        print(f'Creado {self.salida}: {len(puntos)} puntos.')

    @classmethod
    def main(cls):
        carpeta = Path(__file__).resolve().parent
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('entrada', nargs='?', type=Path, default=carpeta / 'etapaEsquema.xml')
        parser.add_argument('salida', nargs='?', type=Path, default=carpeta / 'altimetria.svg')
        args = parser.parse_args()
        cls(args.entrada, args.salida).generar()


if __name__ == '__main__':
    Xml2Altimetria.main()
