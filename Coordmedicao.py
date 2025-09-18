import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import io
import numpy as np
from geopy.distance import geodesic
from datetime import datetime, timedelta
import random
import plotly.express as px
from folium import plugins
import zipfile
import openpyxl

# Configuração da página
st.set_page_config(
    page_title="Rezende Energia - Mapeador de Coordenadas",
    page_icon="⚡",
    layout="wide"
)

# CSS personalizado com as cores da Rezende Energia
st.markdown("""
<style>
    /* Estilo principal da aplicação */
    .main {
        background-color: #ffffff;
    }

    /* Cabeçalho principal */
    .main-header {
        background: linear-gradient(135deg, #000000 0%, #F7931E 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }

    /* Título principal */
    .main-title {
        font-size: 3rem;
        font-weight: bold;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }

    /* Subtítulo */
    .main-subtitle {
        font-size: 1.2rem;
        margin-top: 0.5rem;
        opacity: 0.9;
    }

    /* Cards de métricas */
    .metric-card {
        background: linear-gradient(45deg, #F7931E, #FFB84D);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        text-align: center;
        margin: 0.5rem;
        box-shadow: 0 2px 10px rgba(247,147,30,0.3);
    }

    /* Botões personalizados */
    .stButton > button {
        background: linear-gradient(45deg, #000000, #F7931E);
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: bold;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        background: linear-gradient(45deg, #F7931E, #000000);
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(247,147,30,0.4);
    }

    /* Upload area */
    .uploadedFile {
        border: 2px dashed #F7931E;
        border-radius: 10px;
        background-color: #FFF8F0;
    }

    /* Sidebar customization */
    .css-1d391kg {
        background: linear-gradient(180deg, #000000 0%, #F7931E 100%);
    }

    /* Success messages */
    .stSuccess {
        background-color: #E8F5E8;
        border-left: 4px solid #F7931E;
    }

    /* Info messages */
    .stInfo {
        background-color: #FFF8F0;
        border-left: 4px solid #F7931E;
    }

    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #000000, #F7931E);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        font-weight: bold;
    }

    /* Company footer */
    .company-footer {
        background: linear-gradient(135deg, #000000, #F7931E);
        color: white;
        text-align: center;
        padding: 2rem;
        border-radius: 10px;
        margin-top: 2rem;
    }

    /* DataFrame styling */
    .stDataFrame {
        border: 2px solid #F7931E;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Cabeçalho da empresa
st.markdown("""
<div class="main-header">
    <h1 class="main-title">⚡ REZENDE ENERGIA</h1>
    <p class="main-subtitle">🗺️ MAPEADOR DE COORDENADAS PROFISSIONAL</p>
    <p style="font-size: 0.9rem; margin-top: 1rem;">Importe uma planilha com coordenadas nas colunas BA (latitude) e BB (longitude)</p>
</div>
""", unsafe_allow_html=True)

# Upload do arquivo com estilo personalizado
st.markdown(
    '<div style="background: linear-gradient(45deg, #FFF8F0, #FFFFFF); padding: 1.5rem; border-radius: 10px; border: 2px solid #F7931E; margin: 1rem 0;">',
    unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    "📂 SELECIONE SEU ARQUIVO DE COORDENADAS",
    type=['xlsx', 'xls', 'csv'],
    help="Formatos aceitos: Excel (.xlsx, .xls) e CSV (.csv) | Processamento automático de dados"
)
st.markdown('</div>', unsafe_allow_html=True)


def clean_and_convert_coordinates(df):
    """Limpa e converte coordenadas para formato numérico correto"""
    df_clean = df.copy()
    coord_columns = ['AH', 'BA', 'BB']

    for col in coord_columns:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str)
            df_clean[col] = df_clean[col].str.strip()
            df_clean[col] = df_clean[col].str.replace('\r', '').str.replace('\n', '').str.replace('\t', '')
            df_clean[col] = df_clean[col].str.replace(',', '.')

            if col in ['BA', 'BB']:
                df_clean[col] = df_clean[col].str.replace(r'[^\d\.\-\+]', '', regex=True)

            df_clean[col] = df_clean[col].replace(['', 'nan', 'NaN', 'null', 'NULL', 'none', 'None'], np.nan)

            if col in ['BA', 'BB']:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            else:
                try:
                    numeric_version = pd.to_numeric(df_clean[col], errors='coerce')
                    if numeric_version.notna().sum() > len(numeric_version) * 0.8:
                        df_clean[col] = numeric_version
                except:
                    pass

    return df_clean


def validate_coordinates(df):
    """Valida se as coordenadas estão em ranges válidos"""
    validation_results = {
        'valid_count': 0,
        'invalid_lat': 0,
        'invalid_lon': 0,
        'missing_coords': 0,
        'warnings': []
    }

    valid_coords_mask = (
            df['BA'].notna() &
            df['BB'].notna() &
            (df['BA'] >= -90) & (df['BA'] <= 90) &
            (df['BB'] >= -180) & (df['BB'] <= 180)
    )

    validation_results['valid_count'] = valid_coords_mask.sum()
    validation_results['missing_coords'] = (df['BA'].isna() | df['BB'].isna()).sum()
    validation_results['invalid_lat'] = ((df['BA'] < -90) | (df['BA'] > 90)).sum()
    validation_results['invalid_lon'] = ((df['BB'] < -180) | (df['BB'] > 180)).sum()

    if validation_results['missing_coords'] > 0:
        validation_results['warnings'].append(
            f"⚠️ {validation_results['missing_coords']} linha(s) com coordenadas em branco")

    if validation_results['invalid_lat'] > 0:
        validation_results['warnings'].append(
            f"⚠️ {validation_results['invalid_lat']} latitude(s) fora do range válido (-90 a 90)")

    if validation_results['invalid_lon'] > 0:
        validation_results['warnings'].append(
            f"⚠️ {validation_results['invalid_lon']} longitude(s) fora do range válido (-180 a 180)")

    return validation_results


def create_map_with_enhanced_features(df):
    """Cria o mapa com funcionalidades avançadas e tema Rezende Energia"""
    center_lat = df['BA'].mean()
    center_lon = df['BB'].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap'
    )

    # Camadas com tema empresarial
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name='Modo Claro',
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name='Modo Escuro',
        control=True
    ).add_to(m)

    # Cores da empresa para os pontos
    empresa_colors = ['#F7931E', '#000000', '#FFB84D', '#333333', '#FF6B35']

    for idx, row in df.iterrows():
        lat = row['BA']
        lon = row['BB']
        numero_casa = row.get('AH', 'N/A')

        if pd.notna(lat) and pd.notna(lon):
            tooltip_text = f"⚡ Rezende Energia | 🏠 Casa: {numero_casa} | 📍 {lat:.6f}, {lon:.6f}"

            popup_text = f"""
            <div style="font-family: Arial; font-size: 12px; background: linear-gradient(45deg, #F7931E, #FFB84D); padding: 10px; border-radius: 8px; color: white;">
                <div style="background: rgba(0,0,0,0.8); padding: 8px; border-radius: 5px;">
                    <b>⚡ REZENDE ENERGIA</b><br>
                    <b>🏠 Casa:</b> {numero_casa}<br>
                    <b>🎯 Ponto:</b> {idx + 1}<br>
                    <b>📐 Latitude:</b> {lat:.6f}<br>
                    <b>📐 Longitude:</b> {lon:.6f}
                </div>
            </div>
            """

            color_choice = empresa_colors[idx % len(empresa_colors)]
            folium_color = 'orange' if color_choice == '#F7931E' else 'black'

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=tooltip_text,
                icon=folium.Icon(
                    color=folium_color,
                    icon='flash',
                    prefix='glyphicon'
                )
            ).add_to(m)

    # Plugins avançados
    plugins.Fullscreen(
        position='topright',
        title='Tela Cheia - Rezende Energia',
        title_cancel='Sair da Tela Cheia',
        force_separate_button=True
    ).add_to(m)

    plugins.MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='miles',
        primary_area_unit='sqkilometers',
        secondary_area_unit='acres'
    ).add_to(m)

    plugins.LocateControl(
        position='topleft',
        strings={
            'title': 'Localização Atual',
            'popup': 'Você está aqui!'
        }
    ).add_to(m)

    folium.LayerControl(position='topright').add_to(m)

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
    """Cria um arquivo KMZ com os pontos do mapa - Rezende Energia"""
    kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Rezende Energia - Coordenadas</name>
    <description>Mapeamento de coordenadas - Rezende Energia</description>

    <Style id="rezende-orange">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/orange-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="rezende-black">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/black-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="rezende-yellow">
      <IconStyle>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
'''

    styles = ['rezende-orange', 'rezende-black', 'rezende-yellow']

    for idx, row in df.iterrows():
        lat = row['BA']
        lon = row['BB']
        numero_casa = row.get('AH', 'N/A')

        if pd.notna(lat) and pd.notna(lon):
            style = styles[idx % len(styles)]

            placemark = f'''
    <Placemark>
      <name>Rezende Energia - Casa {numero_casa}</name>
      <description>
        <![CDATA[
          <div style="font-family: Arial;">
            <h3 style="color: #F7931E;">⚡ REZENDE ENERGIA</h3>
            <b>Número da Casa:</b> {numero_casa}<br/>
            <b>Ponto:</b> {idx + 1}<br/>
            <b>Latitude:</b> {lat:.6f}<br/>
            <b>Longitude:</b> {lon:.6f}
          </div>
        ]]>
      </description>
      <styleUrl>#{style}</styleUrl>
      <Point>
        <coordinates>{lon},{lat},0</coordinates>
      </Point>
    </Placemark>'''

            kml_content += placemark

    kml_content += '''
  </Document>
</kml>'''

    kmz_buffer = io.BytesIO()
    with zipfile.ZipFile(kmz_buffer, 'w', zipfile.ZIP_DEFLATED) as kmz_file:
        kmz_file.writestr('doc.kml', kml_content.encode('utf-8'))

    kmz_buffer.seek(0)
    return kmz_buffer.getvalue()


if uploaded_file is not None:
    try:
        # Ler o arquivo
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.markdown(
            f'<div style="background: linear-gradient(45deg, #28a745, #20c997); color: white; padding: 1rem; border-radius: 8px; text-align: center; font-weight: bold;">✅ ARQUIVO CARREGADO COM SUCESSO! {len(df)} linhas encontradas.</div>',
            unsafe_allow_html=True)

        # Verificar colunas
        if len(df.columns) < 54:
            st.markdown(
                f'<div style="background: linear-gradient(45deg, #dc3545, #fd7e14); color: white; padding: 1rem; border-radius: 8px; text-align: center;">❌ ERRO: O arquivo deve ter pelo menos 54 colunas. Encontradas apenas {len(df.columns)} colunas!</div>',
                unsafe_allow_html=True)
            st.info("📋 Colunas necessárias: AH (34), BA (53) e BB (54)")
        else:
            # Processar dados
            df_coords = df.copy()
            df_coords.rename(columns={
                df_coords.columns[33]: 'AH',
                df_coords.columns[52]: 'BA',
                df_coords.columns[53]: 'BB'
            }, inplace=True)

            # Limpeza automática (sem feedback visual)
            df_coords_clean = clean_and_convert_coordinates(df_coords)
            validation = validate_coordinates(df_coords_clean)

            # Avisos importantes apenas
            for warning in validation['warnings']:
                st.warning(warning)

            # Métricas com estilo da empresa
            st.markdown('<div class="section-header">📊 RESUMO DOS DADOS PROCESSADOS</div>', unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'''
                <div class="metric-card">
                    <h2 style="margin: 0; font-size: 2rem;">📍</h2>
                    <h3 style="margin: 0.5rem 0; font-size: 1.8rem;">{len(df_coords_clean)}</h3>
                    <p style="margin: 0;">Total de Pontos</p>
                </div>
                ''', unsafe_allow_html=True)

            with col2:
                st.markdown(f'''
                <div class="metric-card">
                    <h2 style="margin: 0; font-size: 2rem;">✅</h2>
                    <h3 style="margin: 0.5rem 0; font-size: 1.8rem;">{validation['valid_count']}</h3>
                    <p style="margin: 0;">Coordenadas Válidas</p>
                </div>
                ''', unsafe_allow_html=True)

            with col3:
                invalid_coords = len(df_coords_clean) - validation['valid_count']
                st.markdown(f'''
                <div class="metric-card">
                    <h2 style="margin: 0; font-size: 2rem;">⚠️</h2>
                    <h3 style="margin: 0.5rem 0; font-size: 1.8rem;">{invalid_coords}</h3>
                    <p style="margin: 0;">Dados Corrigidos</p>
                </div>
                ''', unsafe_allow_html=True)

            # Processar dados válidos
            df_valid = df_coords_clean[['AH', 'BA', 'BB']].copy()

            valid_coords_mask = (
                    df_valid['BA'].notna() &
                    df_valid['BB'].notna() &
                    (df_valid['BA'] >= -90) & (df_valid['BA'] <= 90) &
                    (df_valid['BB'] >= -180) & (df_valid['BB'] <= 180)
            )

            df_valid = df_valid[valid_coords_mask]

            if len(df_valid) == 0:
                st.markdown(
                    '<div style="background: linear-gradient(45deg, #dc3545, #fd7e14); color: white; padding: 1.5rem; border-radius: 8px; text-align: center; font-weight: bold;">❌ NENHUMA COORDENADA VÁLIDA ENCONTRADA</div>',
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div style="background: linear-gradient(45deg, #28a745, #20c997); color: white; padding: 1rem; border-radius: 8px; text-align: center; font-weight: bold;">🎉 {len(df_valid)} COORDENADAS PROCESSADAS COM SUCESSO!</div>',
                    unsafe_allow_html=True)

                # Preview dos dados
                st.markdown('<div class="section-header">📋 PREVIEW DOS DADOS PROCESSADOS</div>', unsafe_allow_html=True)
                st.dataframe(df_valid.head(10), use_container_width=True)

                # Calcular estatísticas
                if df_valid['BA'].dtype in ['float64', 'int64', 'float32', 'int32'] and len(df_valid) > 0:
                    lat_range = df_valid['BA'].describe()
                    lon_range = df_valid['BB'].describe()

                    # Mapa principal
                    st.markdown('<div class="section-header">🗺️ MAPA INTERATIVO - REZENDE ENERGIA</div>',
                                unsafe_allow_html=True)

                    with st.spinner("⚡ Gerando mapa profissional Rezende Energia..."):
                        map_obj = create_map_with_enhanced_features(df_valid)
                        st_folium(map_obj, width="100%", height=600, returned_objects=["last_clicked"])

                    # Análises avançadas
                    if len(df_valid) > 1:
                        st.markdown('<div class="section-header">📊 ANÁLISES GEOGRÁFICAS AVANÇADAS</div>',
                                    unsafe_allow_html=True)

                        coords = df_valid[['BA', 'BB']].values
                        distances = []

                        if len(coords) > 1:
                            center_point = (df_valid['BA'].mean(), df_valid['BB'].mean())

                            for _, row in df_valid.iterrows():
                                point = (row['BA'], row['BB'])
                                dist = geodesic(center_point, point).kilometers
                                distances.append(dist)

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                st.markdown(f'''
                                <div style="background: linear-gradient(45deg, #000000, #F7931E); color: white; padding: 1.5rem; border-radius: 10px; text-align: center;">
                                    <h3>🎯 MAIS PRÓXIMO</h3>
                                    <h2 style="color: #FFD700;">{min(distances):.2f} km</h2>
                                    <p>do centro geográfico</p>
                                </div>
                                ''', unsafe_allow_html=True)

                            with col2:
                                st.markdown(f'''
                                <div style="background: linear-gradient(45deg, #F7931E, #000000); color: white; padding: 1.5rem; border-radius: 10px; text-align: center;">
                                    <h3>🎯 MAIS DISTANTE</h3>
                                    <h2 style="color: #FFD700;">{max(distances):.2f} km</h2>
                                    <p>do centro geográfico</p>
                                </div>
                                ''', unsafe_allow_html=True)

                            with col3:
                                st.markdown(f'''
                                <div style="background: linear-gradient(45deg, #000000, #F7931E); color: white; padding: 1.5rem; border-radius: 10px; text-align: center;">
                                    <h3>📏 DISTÂNCIA MÉDIA</h3>
                                    <h2 style="color: #FFD700;">{np.mean(distances):.2f} km</h2>
                                    <p>do centro geográfico</p>
                                </div>
                                ''', unsafe_allow_html=True)

                            # Gráfico de distribuição
                            if st.expander("📈 ANÁLISE DE DISTRIBUIÇÃO GEOGRÁFICA"):
                                fig = px.histogram(
                                    x=distances,
                                    nbins=min(20, len(distances)),
                                    title="Distribuição das Distâncias - Rezende Energia",
                                    labels={'x': 'Distância (km)', 'y': 'Quantidade de Pontos'},
                                    color_discrete_sequence=['#F7931E']
                                )
                                fig.update_layout(
                                    height=400,
                                    showlegend=False,
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color='#000000')
                                )
                                st.plotly_chart(fig, use_container_width=True)

                    # Informações detalhadas
                    st.markdown('<div class="section-header">📋 RELATÓRIO TÉCNICO DETALHADO</div>',
                                unsafe_allow_html=True)

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f'''
                        <div style="background: linear-gradient(45deg, #FFF8F0, #FFFFFF); padding: 1.5rem; border: 2px solid #F7931E; border-radius: 10px;">
                            <h4 style="color: #000000;">📐 ESTATÍSTICAS DAS LATITUDES (BA):</h4>
                            <p><strong>Mínimo:</strong> {lat_range['min']:.6f}</p>
                            <p><strong>Máximo:</strong> {lat_range['max']:.6f}</p>
                            <p><strong>Média:</strong> {lat_range['mean']:.6f}</p>
                        </div>
                        ''', unsafe_allow_html=True)

                    with col2:
                        st.markdown(f'''
                        <div style="background: linear-gradient(45deg, #FFF8F0, #FFFFFF); padding: 1.5rem; border: 2px solid #F7931E; border-radius: 10px;">
                            <h4 style="color: #000000;">📐 ESTATÍSTICAS DAS LONGITUDES (BB):</h4>
                            <p><strong>Mínimo:</strong> {lon_range['min']:.6f}</p>
                            <p><strong>Máximo:</strong> {lon_range['max']:.6f}</p>
                            <p><strong>Média:</strong> {lon_range['mean']:.6f}</p>
                        </div>
                        ''', unsafe_allow_html=True)

                    # Downloads
                    st.markdown('<div class="section-header">📥 EXPORTAÇÃO DE DADOS</div>', unsafe_allow_html=True)

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button("📄 BAIXAR DADOS PROCESSADOS (CSV)", key="csv_download"):
                            csv = df_valid.to_csv(index=False)
                            st.download_button(
                                label="💾 Download CSV - Rezende Energia",
                                data=csv,
                                file_name=f"rezende_energia_coordenadas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                    with col2:
                        if st.button("🗺️ EXPORTAR MAPA PROFISSIONAL (KMZ)", key="kmz_download"):
                            kmz_data = create_kmz_file(df_valid)
                            st.download_button(
                                label="💾 Download KMZ - Rezende Energia",
                                data=kmz_data,
                                file_name=f"rezende_energia_mapa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kmz",
                                mime="application/vnd.google-earth.kmz"
                            )

    except Exception as e:
        st.markdown(
            f'<div style="background: linear-gradient(45deg, #dc3545, #fd7e14); color: white; padding: 1.5rem; border-radius: 8px; text-align: center; font-weight: bold;">❌ ERRO NO PROCESSAMENTO: Verifique o formato do arquivo</div>',
            unsafe_allow_html=True)

else:
    # Instruções quando não há arquivo
    st.markdown('<div class="section-header">📝 INSTRUÇÕES DE USO</div>', unsafe_allow_html=True)

    # Card principal de instruções
    st.markdown("""
    <div style="background: linear-gradient(45deg, #FFF8F0, #FFFFFF); padding: 2rem; border: 2px solid #F7931E; border-radius: 15px; margin: 1rem 0;">
        <h3 style="color: #000000; text-align: center; margin-bottom: 1.5rem;">⚡ SISTEMA PROFISSIONAL REZENDE ENERGIA</h3>
    </div>
    """, unsafe_allow_html=True)

    # Requisitos do arquivo
    st.markdown("""
    <div style="background: rgba(247,147,30,0.1); padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #F7931E;">
        <h4 style="color: #000000; margin-top: 0;">📋 REQUISITOS DO ARQUIVO:</h4>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.write("**🏠 Coluna AH (posição 34):** Número da casa/identificação")
        st.write("**📐 Coluna BA (posição 53):** Latitude (coordenada Y)")
        st.write("**📐 Coluna BB (posição 54):** Longitude (coordenada X)")

    with col2:
        st.write("**📊 Mínimo:** 54 colunas no arquivo")
        st.write("**📁 Formatos:** Excel (.xlsx, .xls) e CSV (.csv)")
        st.write("**✅ Compatível:** Qualquer estrutura de dados")

    # Processamento automático
    st.markdown("""
    <div style="background: rgba(0,0,0,0.05); padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #000000;">
        <h4 style="color: #000000; margin-top: 0;">🔄 PROCESSAMENTO AUTOMÁTICO:</h4>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.write("✅ Limpeza automática de espaços")
        st.write("✅ Conversão vírgula → ponto")
        st.write("✅ Remoção de caracteres especiais")

    with col2:
        st.write("✅ Validação de coordenadas geográficas")
        st.write("✅ Correção de formatos de dados")
        st.write("✅ Filtro inteligente de dados válidos")

    # Recursos profissionais
    st.markdown("""
    <div style="background: linear-gradient(45deg, #F7931E, #FFB84D); color: white; padding: 1.5rem; border-radius: 10px; text-align: center; margin: 1rem 0;">
        <h4 style="margin: 0; font-size: 1.3rem;">🎯 RECURSOS PROFISSIONAIS</h4>
        <p style="margin: 0.8rem 0; font-size: 1.1rem;">Mapa Interativo • Análises Geográficas • Exportação KMZ • Relatórios Técnicos</p>
    </div>
    """, unsafe_allow_html=True)

# Rodapé da empresa
st.markdown("""
<div class="company-footer">
    <h2 style="margin: 0;">⚡ REZENDE ENERGIA</h2>
    <p style="margin: 0.5rem 0; font-size: 1.1rem;">Sistema Profissional de Mapeamento de Coordenadas</p>
    <p style="margin: 0; opacity: 0.8;">Desenvolvido com tecnologia Streamlit & Folium | Versão Empresarial 2024</p>
</div>
""", unsafe_allow_html=True)
