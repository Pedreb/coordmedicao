import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import io
import numpy as np
from geopy.distance import geodesic
from datetime import datetime, timedelta
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import plotly.express as px
from functools import lru_cache
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from folium import plugins
import zipfile
import xml.etree.ElementTree as ET

# Configuração da página
st.set_page_config(
    page_title="Mapeador de Coordenadas",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ Mapeador de Coordenadas")
st.markdown("Importe uma planilha com coordenadas nas colunas BA (latitude) e BB (longitude)")

# Upload do arquivo
uploaded_file = st.file_uploader(
    "Escolha um arquivo Excel ou CSV",
    type=['xlsx', 'xls', 'csv'],
    help="O arquivo deve ter as coordenadas na coluna BA (latitude) e BB (longitude)"
)


def generate_colors(n):
    """Gera uma lista de cores distintas para os pontos"""
    colors = [
        'red', 'blue', 'green', 'purple', 'orange', 'darkred',
        'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
        'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen',
        'gray', 'black', 'lightgray'
    ]

    if n <= len(colors):
        return colors[:n]
    else:
        # Se precisar de mais cores, gera cores hexadecimais aleatórias
        extra_colors = []
        for _ in range(n - len(colors)):
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            extra_colors.append(color)
        return colors + extra_colors


def create_map_with_enhanced_features(df):
    """Cria o mapa com funcionalidades avançadas"""
    # Calcular o centro do mapa baseado nas coordenadas
    center_lat = df['BA'].mean()
    center_lon = df['BB'].mean()

    # Criar o mapa com OpenStreetMap como padrão (claro)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap'
    )

    # Adicionar camadas alternativas opcionais
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name='CartoDB Light',
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name='CartoDB Dark',
        control=True
    ).add_to(m)

    # Gerar cores para cada ponto
    colors = generate_enhanced_colors(len(df))

    # Adicionar pontos ao mapa com ícones melhorados
    for idx, row in df.iterrows():
        lat = row['BA']
        lon = row['BB']
        numero_casa = row.get('AH', 'N/A')  # Pegar número da casa ou N/A se vazio

        if pd.notna(lat) and pd.notna(lon):
            # Tooltip que aparece ao passar o mouse
            tooltip_text = f"🏠 Casa: {numero_casa} | 📍 Lat: {lat:.6f}, Lon: {lon:.6f}"

            # Popup que aparece ao clicar
            popup_text = f"""
            <div style="font-family: Arial; font-size: 12px;">
                <b>🏠 Número da Casa:</b> {numero_casa}<br>
                <b>🎯 Ponto:</b> {idx + 1}<br>
                <b>📐 Latitude:</b> {lat:.6f}<br>
                <b>📐 Longitude:</b> {lon:.6f}<br>
                <b>🌍 Coordenadas:</b> {lat:.4f}, {lon:.4f}
            </div>
            """

            # Mapear cores do Plotly para cores do Folium
            folium_color = map_plotly_to_folium_color(colors[idx % len(colors)])

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_text, max_width=280),
                tooltip=tooltip_text,
                icon=folium.Icon(
                    color=folium_color,
                    icon='home',  # Ícone de casa
                    prefix='glyphicon'
                )
            ).add_to(m)

    # Adicionar plugins avançados
    plugins.Fullscreen(
        position='topright',
        title='Tela Cheia',
        title_cancel='Sair da Tela Cheia',
        force_separate_button=True
    ).add_to(m)

    # Adicionar medição de distância
    plugins.MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='miles',
        primary_area_unit='sqkilometers',
        secondary_area_unit='acres'
    ).add_to(m)

    # Adicionar controle de localização
    plugins.LocateControl(
        position='topleft',
        strings={
            'title': 'Mostrar minha localização',
            'popup': 'Você está aqui!'
        }
    ).add_to(m)

    # Adicionar controle de camadas
    folium.LayerControl(position='topright').add_to(m)

    # Adicionar mini mapa
    minimap = plugins.MiniMap(
        tile_layer='OpenStreetMap',
        position='bottomright',
        width=150,
        height=150,
        collapsed_width=25,
        collapsed_height=25
    )
    m.add_child(minimap)

    return m


def create_kmz_file(df):
    """Cria um arquivo KMZ com os pontos do mapa"""

    # Criar o conteúdo KML
    kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Coordenadas Exportadas</name>
    <description>Pontos exportados do Mapeador de Coordenadas</description>

    <!-- Estilos para diferentes cores -->
    <Style id="red-pushpin">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="blue-pushpin">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/blue-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="green-pushpin">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/grn-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="yellow-pushpin">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="purple-pushpin">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/purple-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
'''

    # Estilos disponíveis
    styles = ['red-pushpin', 'blue-pushpin', 'green-pushpin', 'yellow-pushpin', 'purple-pushpin']

    # Adicionar placemarks para cada ponto
    for idx, row in df.iterrows():
        lat = row['BA']
        lon = row['BB']
        numero_casa = row.get('AH', 'N/A')

        if pd.notna(lat) and pd.notna(lon):
            style = styles[idx % len(styles)]

            placemark = f'''
    <Placemark>
      <name>Casa {numero_casa}</name>
      <description>
        <![CDATA[
          <b>Número da Casa:</b> {numero_casa}<br/>
          <b>Ponto:</b> {idx + 1}<br/>
          <b>Latitude:</b> {lat:.6f}<br/>
          <b>Longitude:</b> {lon:.6f}
        ]]>
      </description>
      <styleUrl>#{style}</styleUrl>
      <Point>
        <coordinates>{lon},{lat},0</coordinates>
      </Point>
    </Placemark>'''

            kml_content += placemark

    # Fechar o documento KML
    kml_content += '''
  </Document>
</kml>'''

    # Criar o arquivo KMZ (KML comprimido)
    kmz_buffer = io.BytesIO()

    with zipfile.ZipFile(kmz_buffer, 'w', zipfile.ZIP_DEFLATED) as kmz_file:
        # Adicionar o arquivo KML dentro do ZIP
        kmz_file.writestr('doc.kml', kml_content.encode('utf-8'))

    kmz_buffer.seek(0)
    return kmz_buffer.getvalue()


def map_plotly_to_folium_color(plotly_color):
    """Mapeia cores do Plotly para cores disponíveis no Folium"""
    color_mapping = {
        '#1f77b4': 'blue',  # azul
        '#ff7f0e': 'orange',  # laranja
        '#2ca02c': 'green',  # verde
        '#d62728': 'red',  # vermelho
        '#9467bd': 'purple',  # roxo
        '#8c564b': 'darkred',  # marrom
        '#e377c2': 'pink',  # rosa
        '#7f7f7f': 'gray',  # cinza
        '#bcbd22': 'darkgreen',  # verde escuro
        '#17becf': 'lightblue',  # azul claro
    }

    # Cores disponíveis no Folium
    folium_colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
                     'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                     'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen',
                     'gray', 'black', 'lightgray']

    # Se a cor está no mapeamento, usar ela
    if plotly_color in color_mapping:
        return color_mapping[plotly_color]

    # Senão, usar uma cor aleatória da lista
    return folium_colors[hash(plotly_color) % len(folium_colors)]


def generate_enhanced_colors(n):
    """Gera cores mais vibrantes e distintas"""
    if n <= 10:
        # Usar cores predefinidas do Plotly para melhor distinção
        plotly_colors = px.colors.qualitative.Set1
        return plotly_colors[:n]
    elif n <= 20:
        plotly_colors = px.colors.qualitative.Set3
        return plotly_colors[:n]
    else:
        # Para muitos pontos, usar combinação de paletas
        colors = (px.colors.qualitative.Set1 +
                  px.colors.qualitative.Set2 +
                  px.colors.qualitative.Set3)

        # Se ainda precisar de mais cores, gerar cores HSV
        if n > len(colors):
            extra_colors = []
            for i in range(n - len(colors)):
                hue = (i * 137.5) % 360  # Golden angle para distribuição uniforme
                extra_colors.append(f"hsl({hue}, 70%, 50%)")
            colors.extend(extra_colors)

        return colors[:n]


if uploaded_file is not None:
    try:
        # Ler o arquivo
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success(f"Arquivo carregado com sucesso! {len(df)} linhas encontradas.")

        # Verificar se existem pelo menos 54 colunas (BA=53, BB=54, AH=34, índice base 0: 52, 53, 33)
        if len(df.columns) < 54:
            st.error(f"❌ O arquivo deve ter pelo menos 54 colunas. Encontradas apenas {len(df.columns)} colunas!")
            st.info(
                "Colunas necessárias: AH (coluna 34) para número da casa, BA (coluna 53) para latitude e BB (coluna 54) para longitude")
        else:
            # Renomear as colunas para facilitar o uso
            df_coords = df.copy()
            df_coords.rename(columns={
                df_coords.columns[33]: 'AH',  # Coluna 34 (índice 33) - Número da casa
                df_coords.columns[52]: 'BA',  # Coluna 53 (índice 52) - Latitude
                df_coords.columns[53]: 'BB'  # Coluna 54 (índice 53) - Longitude
            }, inplace=True)
            # Mostrar informações básicas dos dados
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total de pontos", len(df_coords))

            with col2:
                valid_coords = df_coords[['BA', 'BB']].dropna()
                st.metric("Coordenadas válidas", len(valid_coords))

            with col3:
                invalid_coords = len(df_coords) - len(valid_coords)
                st.metric("Coordenadas inválidas", invalid_coords)

            st.info(
                f"📍 Usando coluna {df.columns[33]} (posição 34/AH) como número da casa, coluna {df.columns[52]} (posição 53/BA) como latitude e coluna {df.columns[53]} (posição 54/BB) como longitude")

            # Filtrar apenas coordenadas válidas, mantendo a coluna AH
            df_valid = df_coords[['AH', 'BA', 'BB']].dropna(subset=['BA', 'BB'])

            if len(df_valid) == 0:
                st.error("❌ Nenhuma coordenada válida encontrada!")
            else:
                # Mostrar preview dos dados
                st.subheader("📊 Preview dos dados")
                st.dataframe(df_valid.head(10))

                # Verificar se os valores estão em range válido para coordenadas
                lat_range = df_valid['BA'].describe()
                lon_range = df_valid['BB'].describe()

                if (lat_range['min'] < -90 or lat_range['max'] > 90 or
                        lon_range['min'] < -180 or lon_range['max'] > 180):
                    st.warning(
                        "⚠️ Algumas coordenadas podem estar fora do range válido (lat: -90 a 90, lon: -180 a 180)")

                # Criar e exibir o mapa
                st.subheader("🗺️ Mapa das Coordenadas")

                with st.spinner("Gerando mapa avançado..."):
                    map_obj = create_map_with_enhanced_features(df_valid)
                    st_folium(map_obj, width="100%", height=600, returned_objects=["last_clicked"])

                # Análises adicionais com as novas bibliotecas
                if len(df_valid) > 1:
                    st.subheader("📊 Análises Avançadas")

                    # Calcular estatísticas de distância
                    coords = df_valid[['BA', 'BB']].values
                    distances = []

                    if len(coords) > 1:
                        center_point = (df_valid['BA'].mean(), df_valid['BB'].mean())

                        for _, row in df_valid.iterrows():
                            point = (row['BA'], row['BB'])
                            dist = geodesic(center_point, point).kilometers
                            distances.append(dist)

                        df_valid_copy = df_valid.copy()
                        df_valid_copy['distancia_centro'] = distances

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "🎯 Ponto mais próximo do centro",
                                f"{min(distances):.2f} km"
                            )

                        with col2:
                            st.metric(
                                "🎯 Ponto mais distante do centro",
                                f"{max(distances):.2f} km"
                            )

                        with col3:
                            st.metric(
                                "📏 Distância média do centro",
                                f"{np.mean(distances):.2f} km"
                            )

                        # Gráfico de dispersão das distâncias
                        if st.expander("📈 Visualizar distribuição das distâncias"):
                            fig = px.histogram(
                                x=distances,
                                nbins=min(20, len(distances)),
                                title="Distribuição das Distâncias do Centro",
                                labels={'x': 'Distância (km)', 'y': 'Quantidade de Pontos'}
                            )
                            fig.update_layout(
                                height=400,
                                showlegend=False
                            )
                            st.plotly_chart(fig, use_container_width=True)

                # Opções adicionais
                st.subheader("📋 Informações Detalhadas")

                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Estatísticas das Latitudes (BA):**")
                    st.write(f"Mínimo: {lat_range['min']:.6f}")
                    st.write(f"Máximo: {lat_range['max']:.6f}")
                    st.write(f"Média: {lat_range['mean']:.6f}")

                with col2:
                    st.write("**Estatísticas das Longitudes (BB):**")
                    st.write(f"Mínimo: {lon_range['min']:.6f}")
                    st.write(f"Máximo: {lon_range['max']:.6f}")
                    st.write(f"Média: {lon_range['mean']:.6f}")

                # Download dos arquivos processados
                st.subheader("📥 Downloads")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("📄 Baixar dados válidos (CSV)"):
                        csv = df_valid.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name="coordenadas_processadas.csv",
                            mime="text/csv"
                        )

                with col2:
                    if st.button("🗺️ Exportar mapa (KMZ)"):
                        kmz_data = create_kmz_file(df_valid)
                        st.download_button(
                            label="Download KMZ",
                            data=kmz_data,
                            file_name=f"mapa_coordenadas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz",
                            mime="application/vnd.google-earth.kmz"
                        )

    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {str(e)}")
        st.info("Verifique se o arquivo está no formato correto e não está corrompido.")

else:
    st.info("👆 Faça upload de um arquivo para começar")

    # Mostrar exemplo de formato esperado
    st.subheader("📝 Formato esperado do arquivo")

    st.markdown("""
    **Instruções:**
    - A coluna **AH** (posição 34) deve conter o número da casa
    - A coluna **BA** (posição 53) deve conter as latitudes
    - A coluna **BB** (posição 54) deve conter as longitudes  
    - O arquivo deve ter pelo menos 54 colunas
    - Formatos aceitos: Excel (.xlsx, .xls) e CSV (.csv)
    - Coordenadas inválidas ou vazias serão automaticamente filtradas

    **Exemplo de estrutura:**
    - Coluna A, B, C... até AH (número da casa)... BA (latitude), BB (longitude)
    - O programa buscará automaticamente as colunas nas posições 34, 53 e 54
    - **Ao passar o mouse:** mostra número da casa e coordenadas
    - **Ao clicar:** mostra informações detalhadas
    """)

# Rodapé
st.markdown("---")
st.markdown("Desenvolvido com Streamlit e Folium")