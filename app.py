import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import csv
import io

# Configuração da página
st.set_page_config(
    page_title="Ferramenta de Monitorização de Stock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Definição de constantes
INDICADORES = [
    "Rotação", "Stock Liquido", "Stock Provision", 
    "Stock in Transit", "Stock Bruto", "Vendas", 
    "MFO", "Quebra", "COGS"
]

GRANULARIDADES = [
    "Core", "New Business", "Services + Others", "B2B"
]

GRANULARIDADES_COM_TOTAL = ["Total"] + GRANULARIDADES

PERIODOS_ANALISE = [
    "Budget", "Last Year", "Real + Projeção", "Introduzido"
]

PERIODOS_ACUMULADOS = ["YTD", "EOP"]

# Função para criar estrutura de dados inicial
def criar_estrutura_dados():
    # Verificar se já existe um arquivo de dados
    if os.path.exists('dados_stock.json'):
        with open('dados_stock.json', 'r') as f:
            return json.load(f)
    
    # Criar estrutura de dados vazia
    dados = {
        "semanas": {},
        "meses": {}
    }
    
    # Obter data atual
    hoje = datetime.now()
    
    # Criar estrutura para as próximas 12 semanas
    for i in range(12):
        data_inicio = hoje + timedelta(weeks=i)
        semana = data_inicio.strftime("%Y-W%W")
        
        dados["semanas"][semana] = {}
        
        for granularidade in GRANULARIDADES:
            dados["semanas"][semana][granularidade] = {}
            
            for indicador in INDICADORES:
                dados["semanas"][semana][granularidade][indicador] = {}
                
                for periodo in PERIODOS_ANALISE:
                    dados["semanas"][semana][granularidade][indicador][periodo] = 0.0
        
        # Adicionar Total (será calculado automaticamente)
        dados["semanas"][semana]["Total"] = {}
        for indicador in INDICADORES:
            dados["semanas"][semana]["Total"][indicador] = {}
            for periodo in PERIODOS_ANALISE:
                dados["semanas"][semana]["Total"][indicador][periodo] = 0.0
    
    # Criar estrutura para os próximos 3 meses
    for i in range(3):
        data_inicio = hoje.replace(day=1) + timedelta(days=32*i)
        mes = data_inicio.strftime("%Y-%m")
        
        dados["meses"][mes] = {}
        
        for granularidade in GRANULARIDADES_COM_TOTAL:
            dados["meses"][mes][granularidade] = {}
            
            for indicador in INDICADORES:
                dados["meses"][mes][granularidade][indicador] = {}
                
                for periodo in PERIODOS_ANALISE:
                    dados["meses"][mes][granularidade][indicador][periodo] = 0.0
                    
                for periodo_acumulado in PERIODOS_ACUMULADOS:
                    dados["meses"][mes][granularidade][indicador][f"{periodo_acumulado}"] = {}
                    for periodo in PERIODOS_ANALISE:
                        dados["meses"][mes][granularidade][indicador][f"{periodo_acumulado}"][periodo] = 0.0
    
    # Salvar estrutura inicial
    with open('dados_stock.json', 'w') as f:
        json.dump(dados, f, indent=4)
    
    return dados

# Função para salvar dados
def salvar_dados(dados):
    with open('dados_stock.json', 'w') as f:
        json.dump(dados, f, indent=4)

# Função para calcular COGS
def calcular_cogs(vendas, mfo, quebra):
    return vendas - mfo - quebra

# Função para calcular rotação de stock
def calcular_rotacao(stock_liquido_medio, cogs_acumulado):
    if stock_liquido_medio == 0 or cogs_acumulado == 0:
        return 0
    return stock_liquido_medio / cogs_acumulado

# Função para calcular o Total como soma das granularidades
def calcular_total(dados, semana, indicador, periodo):
    total = 0.0
    for granularidade in GRANULARIDADES:
        total += dados["semanas"][semana][granularidade][indicador][periodo]
    return total

# Função para atualizar todos os totais
def atualizar_totais(dados):
    # Para cada semana
    for semana in dados["semanas"]:
        # Para cada indicador
        for indicador in INDICADORES:
            # Para cada período
            for periodo in PERIODOS_ANALISE:
                # Calcular o total como soma das granularidades
                dados["semanas"][semana]["Total"][indicador][periodo] = calcular_total(dados, semana, indicador, periodo)
    
    return dados

# Função para atualizar COGS
def atualizar_cogs(dados):
    # Para cada semana
    for semana in dados["semanas"]:
        # Para cada granularidade
        for granularidade in GRANULARIDADES_COM_TOTAL:
            # Para cada período
            for periodo in PERIODOS_ANALISE:
                # Calcular COGS = Vendas - MFO - Quebra
                vendas = dados["semanas"][semana][granularidade]["Vendas"][periodo]
                mfo = dados["semanas"][semana][granularidade]["MFO"][periodo]
                quebra = dados["semanas"][semana][granularidade]["Quebra"][periodo]
                dados["semanas"][semana][granularidade]["COGS"][periodo] = calcular_cogs(vendas, mfo, quebra)
    
    return dados

# Função para atualizar resumo mensal
def atualizar_resumo_mensal(dados):
    # Para cada mês
    for mes in dados["meses"]:
        # Encontrar semanas que pertencem a este mês
        semanas_do_mes = []
        for semana in dados["semanas"]:
            # Extrair ano e número da semana
            ano, num_semana = semana.split("-W")
            # Converter para data (primeiro dia da semana)
            data_semana = datetime.strptime(f"{ano}-{num_semana}-1", "%Y-%W-%w")
            # Verificar se o mês da data corresponde ao mês atual
            if data_semana.strftime("%Y-%m") == mes:
                semanas_do_mes.append(semana)
        
        # Para cada granularidade
        for granularidade in GRANULARIDADES_COM_TOTAL:
            # Para cada indicador
            for indicador in INDICADORES:
                # Calcular média/soma das semanas para o mês
                for periodo in PERIODOS_ANALISE:
                    valores = [dados["semanas"][s][granularidade][indicador][periodo] for s in semanas_do_mes]
                    if valores:
                        # Para vendas, MFO, quebra e COGS, somamos os valores
                        if indicador in ["Vendas", "MFO", "Quebra", "COGS"]:
                            dados["meses"][mes][granularidade][indicador][periodo] = sum(valores)
                        # Para stocks, calculamos a média
                        else:
                            dados["meses"][mes][granularidade][indicador][periodo] = sum(valores) / len(valores)
                
                # Calcular rotação se for o indicador "Rotação"
                if indicador == "Rotação":
                    for periodo in PERIODOS_ANALISE:
                        stock_liquido_medio = dados["meses"][mes][granularidade]["Stock Liquido"][periodo]
                        cogs_acumulado = dados["meses"][mes][granularidade]["COGS"][periodo]
                        dados["meses"][mes][granularidade]["Rotação"][periodo] = calcular_rotacao(stock_liquido_medio, cogs_acumulado)
                
                # Atualizar YTD e EOP
                for periodo in PERIODOS_ANALISE:
                    # EOP é o valor do final do período (último valor)
                    dados["meses"][mes][granularidade][indicador]["EOP"][periodo] = dados["meses"][mes][granularidade][indicador][periodo]
                    
                    # YTD é acumulado desde o início do ano
                    # Simplificação: usamos o mesmo valor para demonstração
                    dados["meses"][mes][granularidade][indicador]["YTD"][periodo] = dados["meses"][mes][granularidade][indicador][periodo]
    
    return dados

# Função para processar importação de dados CSV
def processar_importacao_csv(conteudo_csv):
    dados_importados = []
    csv_reader = csv.DictReader(io.StringIO(conteudo_csv))
    for row in csv_reader:
        dados_importados.append(row)
    return dados_importados

# Função para criar gráficos
def criar_grafico(dados, periodo_tipo, periodo, granularidade, indicador, periodos_analise):
    if periodo_tipo == "semanas":
        df = pd.DataFrame({
            "Período": list(dados["semanas"].keys()),
            **{p: [dados["semanas"][s][granularidade][indicador][p] for s in dados["semanas"]] for p in periodos_analise}
        })
    else:  # meses
        df = pd.DataFrame({
            "Período": list(dados["meses"].keys()),
            **{p: [dados["meses"][m][granularidade][indicador][p] for m in dados["meses"]] for p in periodos_analise}
        })
    
    fig = px.line(df, x="Período", y=periodos_analise, title=f"{indicador} - {granularidade}")
    fig.update_layout(height=400)
    return fig

# Função para criar gráficos de resumo mensal
def criar_grafico_resumo_mensal(dados, mes, granularidade, indicador, tipo_acumulado=None):
    if tipo_acumulado:
        df = pd.DataFrame({
            "Período": PERIODOS_ANALISE,
            "Valor": [dados["meses"][mes][granularidade][indicador][tipo_acumulado][p] for p in PERIODOS_ANALISE]
        })
        titulo = f"{indicador} - {granularidade} ({tipo_acumulado})"
    else:
        df = pd.DataFrame({
            "Período": PERIODOS_ANALISE,
            "Valor": [dados["meses"][mes][granularidade][indicador][p] for p in PERIODOS_ANALISE]
        })
        titulo = f"{indicador} - {granularidade}"
    
    fig = px.bar(df, x="Período", y="Valor", title=titulo)
    fig.update_layout(height=300)
    return fig

# Inicializar dados
dados = criar_estrutura_dados()

# Interface da aplicação
st.title("Ferramenta de Monitorização de Stock")

# Sidebar para navegação
st.sidebar.title("Navegação")
pagina = st.sidebar.radio("Selecione a página:", ["Visão Semanal", "Resumo Mensal", "Introdução de Dados", "Importação de Dados"])

if pagina == "Visão Semanal":
    st.header("Visão Semanal")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        semana_selecionada = st.selectbox("Selecione a Semana:", list(dados["semanas"].keys()))
    with col2:
        granularidade_selecionada = st.selectbox("Selecione a Granularidade:", GRANULARIDADES_COM_TOTAL)
    with col3:
        indicador_selecionado = st.selectbox("Selecione o Indicador:", INDICADORES)
    
    periodos_selecionados = st.multiselect("Selecione os Períodos de Análise:", PERIODOS_ANALISE, default=PERIODOS_ANALISE)
    
    # Exibir gráfico
    if periodos_selecionados:
        grafico = criar_grafico(dados, "semanas", semana_selecionada, granularidade_selecionada, indicador_selecionado, periodos_selecionados)
        st.plotly_chart(grafico, use_container_width=True)
    
    # Exibir tabela de dados
    st.subheader(f"Dados da Semana {semana_selecionada}")
    
    # Criar DataFrame para exibição
    dados_tabela = []
    for indicador in INDICADORES:
        linha = {"Indicador": indicador}
        for periodo in PERIODOS_ANALISE:
            linha[periodo] = dados["semanas"][semana_selecionada][granularidade_selecionada][indicador][periodo]
        dados_tabela.append(linha)
    
    df_tabela = pd.DataFrame(dados_tabela)
    st.dataframe(df_tabela, use_container_width=True)

elif pagina == "Resumo Mensal":
    st.header("Resumo Mensal")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        mes_selecionado = st.selectbox("Selecione o Mês:", list(dados["meses"].keys()))
    with col2:
        granularidade_selecionada = st.selectbox("Selecione a Granularidade:", GRANULARIDADES_COM_TOTAL)
    with col3:
        tipo_acumulado = st.selectbox("Selecione o Tipo de Período:", ["Mensal", "YTD", "EOP"])
    
    # Exibir gráficos para cada indicador
    st.subheader(f"Resumo de {mes_selecionado} - {granularidade_selecionada}")
    
    # Organizar gráficos em grid
    num_colunas = 3
    num_indicadores = len(INDICADORES)
    num_linhas = (num_indicadores + num_colunas - 1) // num_colunas
    
    for i in range(num_linhas):
        cols = st.columns(num_colunas)
        for j in range(num_colunas):
            idx = i * num_colunas + j
            if idx < num_indicadores:
                indicador = INDICADORES[idx]
                with cols[j]:
                    if tipo_acumulado == "Mensal":
                        grafico = criar_grafico_resumo_mensal(dados, mes_selecionado, granularidade_selecionada, indicador)
                    else:
                        grafico = criar_grafico_resumo_mensal(dados, mes_selecionado, granularidade_selecionada, indicador, tipo_acumulado)
                    st.plotly_chart(grafico, use_container_width=True)
    
    # Exibir tabela de dados
    st.subheader(f"Dados do Mês {mes_selecionado}")
    
    # Criar DataFrame para exibição
    dados_tabela = []
    for indicador in INDICADORES:
        linha = {"Indicador": indicador}
        if tipo_acumulado == "Mensal":
            for periodo in PERIODOS_ANALISE:
                linha[periodo] = dados["meses"][mes_selecionado][granularidade_selecionada][indicador][periodo]
        else:
            for periodo in PERIODOS_ANALISE:
                linha[periodo] = dados["meses"][mes_selecionado][granularidade_selecionada][indicador][tipo_acumulado][periodo]
        dados_tabela.append(linha)
    
    df_tabela = pd.DataFrame(dados_tabela)
    st.dataframe(df_tabela, use_container_width=True)

elif pagina == "Introdução de Dados":
    st.header("Introdução de Dados para Simulação")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        semana_selecionada = st.selectbox("Selecione a Semana:", list(dados["semanas"].keys()))
    
    with col2:
        granularidade_selecionada = st.selectbox("Selecione a Granularidade:", GRANULARIDADES)
        st.info("O Total é calculado automaticamente como soma das outras granularidades.")
    
    # Formulário para introdução de dados
    with st.form("formulario_dados"):
        st.subheader(f"Introduzir Dados para {semana_selecionada} - {granularidade_selecionada}")
        
        # Criar campos para cada indicador
        valores = {}
        for indicador in INDICADORES:
            if indicador not in ["Rotação", "COGS"]:  # Rotação e COGS são calculados automaticamente
                valores[indicador] = st.number_input(
                    f"{indicador} (Introduzido)", 
                    value=float(dados["semanas"][semana_selecionada][granularidade_selecionada][indicador]["Introduzido"]),
                    format="%.2f"
                )
        
        # Botão de submissão
        submitted = st.form_submit_button("Salvar Dados")
        
        if submitted:
            # Atualizar dados
            for indicador, valor in valores.items():
                dados["semanas"][semana_selecionada][granularidade_selecionada][indicador]["Introduzido"] = valor
            
            # Atualizar totais
            dados = atualizar_totais(dados)
            
            # Atualizar COGS
            dados = atualizar_cogs(dados)
            
            # Calcular rotação
            for granularidade in GRANULARIDADES_COM_TOTAL:
                stock_liquido = dados["semanas"][semana_selecionada][granularidade]["Stock Liquido"]["Introduzido"]
                cogs = dados["semanas"][semana_selecionada][granularidade]["COGS"]["Introduzido"]
                dados["semanas"][semana_selecionada][granularidade]["Rotação"]["Introduzido"] = calcular_rotacao(stock_liquido, cogs)
            
            # Atualizar resumo mensal
            dados = atualizar_resumo_mensal(dados)
            
            # Salvar dados
            salvar_dados(dados)
            
            st.success("Dados salvos com sucesso!")
    
    # Exibir tabela atual
    st.subheader("Dados Atuais")
    
    # Criar tabela para todas as granularidades
    dados_atuais = []
    for granularidade in GRANULARIDADES_COM_TOTAL:
        linha = {"Granularidade": granularidade}
        for indicador in INDICADORES:
            linha[indicador] = dados["semanas"][semana_selecionada][granularidade][indicador]["Introduzido"]
        dados_atuais.append(linha)
    
    df_atual = pd.DataFrame(dados_atuais)
    st.dataframe(df_atual, use_container_width=True)

elif pagina == "Importação de Dados":
    st.header("Importação Massiva de Dados")
    
    st.info("""
    Utilize esta página para importar dados em massa. 
    
    O arquivo CSV deve ter o seguinte formato:
    - Semana (formato: YYYY-WXX)
    - Granularidade (Core, New Business, Services + Others, B2B)
    - Indicador (Stock Liquido, Stock Provision, Stock in Transit, Stock Bruto, Vendas, MFO, Quebra)
    - Período (Budget, Last Year, Real + Projeção, Introduzido)
    - Valor (número decimal)
    
    Exemplo:
    ```
    Semana,Granularidade,Indicador,Periodo,Valor
    2025-W22,Core,Stock Liquido,Introduzido,1000.5
    2025-W22,Core,Vendas,Introduzido,500.25
    ```
    
    Nota: Os valores de COGS e Rotação serão calculados automaticamente.
    """)
    
    # Upload de arquivo CSV
    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type="csv")
    
    if uploaded_file is not None:
        # Ler o conteúdo do arquivo
        conteudo = uploaded_file.getvalue().decode("utf-8")
        
        # Processar o CSV
        try:
            dados_importados = processar_importacao_csv(conteudo)
            
            # Exibir prévia dos dados
            st.subheader("Prévia dos Dados")
            df_preview = pd.DataFrame(dados_importados)
            st.dataframe(df_preview, use_container_width=True)
            
            # Botão para confirmar importação
            if st.button("Confirmar Importação"):
                # Atualizar dados com os valores importados
                for row in dados_importados:
                    semana = row.get("Semana")
                    granularidade = row.get("Granularidade")
                    indicador = row.get("Indicador")
                    periodo = row.get("Periodo")
                    valor = float(row.get("Valor", 0))
                    
                    # Verificar se os valores são válidos
                    if (semana in dados["semanas"] and 
                        granularidade in GRANULARIDADES and 
                        indicador in INDICADORES and 
                        indicador not in ["Rotação", "COGS"] and 
                        periodo in PERIODOS_ANALISE):
                        
                        dados["semanas"][semana][granularidade][indicador][periodo] = valor
                
                # Atualizar totais
                dados = atualizar_totais(dados)
                
                # Atualizar COGS
                dados = atualizar_cogs(dados)
                
                # Calcular rotação
                for semana in dados["semanas"]:
                    for granularidade in GRANULARIDADES_COM_TOTAL:
                        for periodo in PERIODOS_ANALISE:
                            stock_liquido = dados["semanas"][semana][granularidade]["Stock Liquido"][periodo]
                            cogs = dados["semanas"][semana][granularidade]["COGS"][periodo]
                            dados["semanas"][semana][granularidade]["Rotação"][periodo] = calcular_rotacao(stock_liquido, cogs)
                
                # Atualizar resumo mensal
                dados = atualizar_resumo_mensal(dados)
                
                # Salvar dados
                salvar_dados(dados)
                
                st.success("Dados importados com sucesso!")
        
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {str(e)}")
    
    # Exemplo de template para download
    st.subheader("Template para Importação")
    
    template_data = [
        {"Semana": "2025-W22", "Granularidade": "Core", "Indicador": "Stock Liquido", "Periodo": "Introduzido", "Valor": "1000.5"},
        {"Semana": "2025-W22", "Granularidade": "Core", "Indicador": "Vendas", "Periodo": "Introduzido", "Valor": "500.25"},
        {"Semana": "2025-W22", "Granularidade": "Core", "Indicador": "MFO", "Periodo": "Introduzido", "Valor": "50.0"},
        {"Semana": "2025-W22", "Granularidade": "Core", "Indicador": "Quebra", "Periodo": "Introduzido", "Valor": "10.0"}
    ]
    
    df_template = pd.DataFrame(template_data)
    
    # Converter para CSV
    csv = df_template.to_csv(index=False)
    
    # Botão para download do template
    st.download_button(
        label="Download Template CSV",
        data=csv,
        file_name="template_importacao.csv",
        mime="text/csv"
    )

# Rodapé
st.markdown("---")
st.markdown("Ferramenta de Monitorização de Stock © 2025")
