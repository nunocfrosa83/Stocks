import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
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

REGIOES = [
    "PT", "ES Mainland", "ES Canárias"
]

REGIOES_COM_IBERICA = REGIOES + ["Ibérica"]

PERIODOS_ANALISE = [
    "Budget", "Last Year", "Real + Projeção", "Introduzido"
]

PERIODOS_ACUMULADOS = ["YTD", "EOP"]

# Função para calcular dias acumulados desde o início do ano
def calcular_dias_acumulados(data_str):
    # Converter string de semana para data
    if "W" in data_str:  # Formato de semana
        ano, semana = data_str.split("-W")
        # Primeiro dia da semana
        primeiro_dia_semana = datetime.strptime(f"{ano}-{semana}-1", "%Y-%W-%w").date()
        # Último dia da semana (domingo)
        ultimo_dia_semana = primeiro_dia_semana + timedelta(days=6)
        data = ultimo_dia_semana
    else:  # Formato de mês
        ano, mes = data_str.split("-")
        # Primeiro dia do próximo mês
        if mes == "12":
            primeiro_dia_proximo_mes = date(int(ano) + 1, 1, 1)
        else:
            primeiro_dia_proximo_mes = date(int(ano), int(mes) + 1, 1)
        # Último dia do mês atual (um dia antes do primeiro dia do próximo mês)
        ultimo_dia_mes = primeiro_dia_proximo_mes - timedelta(days=1)
        data = ultimo_dia_mes
    
    # Primeiro dia do ano
    primeiro_dia_ano = date(data.year, 1, 1)
    
    # Calcular dias acumulados
    dias_acumulados = (data - primeiro_dia_ano).days + 1
    
    return dias_acumulados

# Função para criar estrutura de dados inicial
def criar_estrutura_dados():
    # Verificar se já existe um arquivo de dados
    if os.path.exists('dados_stock_v2.json'):
        with open('dados_stock_v2.json', 'r') as f:
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
        
        # Para cada região
        for regiao in REGIOES:
            dados["semanas"][semana][regiao] = {}
            
            # Para cada granularidade
            for granularidade in GRANULARIDADES:
                dados["semanas"][semana][regiao][granularidade] = {}
                
                # Para cada indicador
                for indicador in INDICADORES:
                    dados["semanas"][semana][regiao][granularidade][indicador] = {}
                    
                    # Para cada período
                    for periodo in PERIODOS_ANALISE:
                        dados["semanas"][semana][regiao][granularidade][indicador][periodo] = 0.0
            
            # Adicionar Total para cada região (será calculado automaticamente)
            dados["semanas"][semana][regiao]["Total"] = {}
            for indicador in INDICADORES:
                dados["semanas"][semana][regiao]["Total"][indicador] = {}
                for periodo in PERIODOS_ANALISE:
                    dados["semanas"][semana][regiao]["Total"][indicador][periodo] = 0.0
        
        # Adicionar região Ibérica (será calculada automaticamente)
        dados["semanas"][semana]["Ibérica"] = {}
        for granularidade in GRANULARIDADES_COM_TOTAL:
            dados["semanas"][semana]["Ibérica"][granularidade] = {}
            for indicador in INDICADORES:
                dados["semanas"][semana]["Ibérica"][granularidade][indicador] = {}
                for periodo in PERIODOS_ANALISE:
                    dados["semanas"][semana]["Ibérica"][granularidade][indicador][periodo] = 0.0
    
    # Criar estrutura para os próximos 3 meses
    for i in range(3):
        data_inicio = hoje.replace(day=1) + timedelta(days=32*i)
        mes = data_inicio.strftime("%Y-%m")
        
        dados["meses"][mes] = {}
        
        # Para cada região
        for regiao in REGIOES:
            dados["meses"][mes][regiao] = {}
            
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                dados["meses"][mes][regiao][granularidade] = {}
                
                # Para cada indicador
                for indicador in INDICADORES:
                    dados["meses"][mes][regiao][granularidade][indicador] = {}
                    
                    # Para cada período
                    for periodo in PERIODOS_ANALISE:
                        dados["meses"][mes][regiao][granularidade][indicador][periodo] = 0.0
                        
                    # Para cada período acumulado
                    for periodo_acumulado in PERIODOS_ACUMULADOS:
                        dados["meses"][mes][regiao][granularidade][indicador][f"{periodo_acumulado}"] = {}
                        for periodo in PERIODOS_ANALISE:
                            dados["meses"][mes][regiao][granularidade][indicador][f"{periodo_acumulado}"][periodo] = 0.0
        
        # Adicionar região Ibérica (será calculada automaticamente)
        dados["meses"][mes]["Ibérica"] = {}
        for granularidade in GRANULARIDADES_COM_TOTAL:
            dados["meses"][mes]["Ibérica"][granularidade] = {}
            for indicador in INDICADORES:
                dados["meses"][mes]["Ibérica"][granularidade][indicador] = {}
                for periodo in PERIODOS_ANALISE:
                    dados["meses"][mes]["Ibérica"][granularidade][indicador][periodo] = 0.0
                
                # Para cada período acumulado
                for periodo_acumulado in PERIODOS_ACUMULADOS:
                    dados["meses"][mes]["Ibérica"][granularidade][indicador][f"{periodo_acumulado}"] = {}
                    for periodo in PERIODOS_ANALISE:
                        dados["meses"][mes]["Ibérica"][granularidade][indicador][f"{periodo_acumulado}"][periodo] = 0.0
    
    # Salvar estrutura inicial
    with open('dados_stock_v2.json', 'w') as f:
        json.dump(dados, f, indent=4)
    
    return dados

# Função para salvar dados
def salvar_dados(dados):
    with open('dados_stock_v2.json', 'w') as f:
        json.dump(dados, f, indent=4)

# Função para calcular COGS
def calcular_cogs(vendas, mfo, quebra):
    return vendas - mfo - quebra

# Função para calcular rotação de stock
def calcular_rotacao(stock_liquido_medio, cogs_acumulado, dias_acumulados):
    if stock_liquido_medio == 0 or cogs_acumulado == 0:
        return 0
    return (stock_liquido_medio / cogs_acumulado) * dias_acumulados

# Função para calcular o Total como soma das granularidades
def calcular_total(dados, periodo_tipo, periodo, regiao, indicador, periodo_analise, periodo_acumulado=None):
    total = 0.0
    for granularidade in GRANULARIDADES:
        try:
            if periodo_acumulado:
                # Se estamos a lidar com período acumulado (YTD, EOP)
                valor = dados[periodo_tipo][periodo][regiao][granularidade][indicador][periodo_acumulado][periodo_analise]
            else:
                # Período normal
                valor = dados[periodo_tipo][periodo][regiao][granularidade][indicador][periodo_analise]
            
            # Garantir que estamos a somar apenas valores numéricos
            if isinstance(valor, (int, float)):
                total += valor
            else:
                print(f"Aviso: Valor não numérico encontrado em {periodo_tipo}/{periodo}/{regiao}/{granularidade}/{indicador}/{periodo_analise}")
        except Exception as e:
            print(f"Erro ao calcular Total: {e}")
    return total

# Função para calcular a região Ibérica como soma das regiões
def calcular_iberica(dados, periodo_tipo, periodo, granularidade, indicador, periodo_analise, periodo_acumulado=None):
    total = 0.0
    for regiao in REGIOES:
        try:
            if periodo_acumulado:
                # Se estamos a lidar com período acumulado (YTD, EOP)
                valor = dados[periodo_tipo][periodo][regiao][granularidade][indicador][periodo_acumulado][periodo_analise]
            else:
                # Período normal
                valor = dados[periodo_tipo][periodo][regiao][granularidade][indicador][periodo_analise]
            
            # Garantir que estamos a somar apenas valores numéricos
            if isinstance(valor, (int, float)):
                total += valor
            else:
                print(f"Aviso: Valor não numérico encontrado em {periodo_tipo}/{periodo}/{regiao}/{granularidade}/{indicador}/{periodo_analise}")
        except Exception as e:
            print(f"Erro ao calcular Ibérica: {e}")
    return total

# Função para atualizar todos os totais
def atualizar_totais(dados):
    # Para cada semana
    for semana in dados["semanas"]:
        # Para cada região (exceto Ibérica)
        for regiao in REGIOES:
            # Para cada indicador
            for indicador in INDICADORES:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Calcular o total como soma das granularidades
                    dados["semanas"][semana][regiao]["Total"][indicador][periodo] = calcular_total(dados, "semanas", semana, regiao, indicador, periodo)
        
        # Calcular região Ibérica como soma das regiões
        for granularidade in GRANULARIDADES_COM_TOTAL:
            for indicador in INDICADORES:
                for periodo in PERIODOS_ANALISE:
                    dados["semanas"][semana]["Ibérica"][granularidade][indicador][periodo] = calcular_iberica(dados, "semanas", semana, granularidade, indicador, periodo)
    
    # Para cada mês
    for mes in dados["meses"]:
        # Para cada região (exceto Ibérica)
        for regiao in REGIOES:
            # Para cada indicador
            for indicador in INDICADORES:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Calcular o total como soma das granularidades
                    dados["meses"][mes][regiao]["Total"][indicador][periodo] = calcular_total(dados, "meses", mes, regiao, indicador, periodo)
                
                # Para cada período acumulado
                for periodo_acumulado in PERIODOS_ACUMULADOS:
                    for periodo in PERIODOS_ANALISE:
                        dados["meses"][mes][regiao]["Total"][indicador][periodo_acumulado][periodo] = calcular_total(dados, "meses", mes, regiao, indicador, periodo, periodo_acumulado)
        
        # Calcular região Ibérica como soma das regiões
        for granularidade in GRANULARIDADES_COM_TOTAL:
            for indicador in INDICADORES:
                for periodo in PERIODOS_ANALISE:
                    dados["meses"][mes]["Ibérica"][granularidade][indicador][periodo] = calcular_iberica(dados, "meses", mes, granularidade, indicador, periodo)
                                 # Para cada período acumulado
                for periodo_acumulado in PERIODOS_ACUMULADOS:
                    for periodo in PERIODOS_ANALISE:
                        dados["meses"][mes]["Ibérica"][granularidade][indicador][periodo_acumulado][periodo] = calcular_iberica(dados, "meses", mes, granularidade, indicador, periodo, periodo_acumulado)
    
    return dados

# Função para atualizar COGS
def atualizar_cogs(dados):
    # Para cada semana
    for semana in dados["semanas"]:
        # Para cada região
        for regiao in REGIOES_COM_IBERICA:
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Calcular COGS = Vendas - MFO - Quebra
                    vendas = dados["semanas"][semana][regiao][granularidade]["Vendas"][periodo]
                    mfo = dados["semanas"][semana][regiao][granularidade]["MFO"][periodo]
                    quebra = dados["semanas"][semana][regiao][granularidade]["Quebra"][periodo]
                    dados["semanas"][semana][regiao][granularidade]["COGS"][periodo] = calcular_cogs(vendas, mfo, quebra)
    
    # Para cada mês
    for mes in dados["meses"]:
        # Para cada região
        for regiao in REGIOES_COM_IBERICA:
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Calcular COGS = Vendas - MFO - Quebra
                    vendas = dados["meses"][mes][regiao][granularidade]["Vendas"][periodo]
                    mfo = dados["meses"][mes][regiao][granularidade]["MFO"][periodo]
                    quebra = dados["meses"][mes][regiao][granularidade]["Quebra"][periodo]
                    dados["meses"][mes][regiao][granularidade]["COGS"][periodo] = calcular_cogs(vendas, mfo, quebra)
                
                # Para cada período acumulado
                for periodo_acumulado in PERIODOS_ACUMULADOS:
                    for periodo in PERIODOS_ANALISE:
                        vendas = dados["meses"][mes][regiao][granularidade]["Vendas"][periodo_acumulado][periodo]
                        mfo = dados["meses"][mes][regiao][granularidade]["MFO"][periodo_acumulado][periodo]
                        quebra = dados["meses"][mes][regiao][granularidade]["Quebra"][periodo_acumulado][periodo]
                        dados["meses"][mes][regiao][granularidade]["COGS"][periodo_acumulado][periodo] = calcular_cogs(vendas, mfo, quebra)
    
    return dados

# Função para calcular stock líquido médio YTD
def calcular_stock_liquido_medio_ytd(dados, data_atual, regiao, granularidade, periodo):
    # Converter data_atual para datetime
    if "W" in data_atual:  # Formato de semana
        ano, semana = data_atual.split("-W")
        data = datetime.strptime(f"{ano}-{semana}-1", "%Y-%W-%w").date()
    else:  # Formato de mês
        data = datetime.strptime(data_atual + "-01", "%Y-%m-%d").date()
    
    # Primeiro dia do ano
    primeiro_dia_ano = date(data.year, 1, 1)
    
    # Calcular média do stock líquido desde o início do ano até a data atual
    stock_liquido_total = 0
    count = 0
    
    # Para semanas
    for semana in dados["semanas"]:
        # Converter semana para data
        ano_s, semana_s = semana.split("-W")
        data_semana = datetime.strptime(f"{ano_s}-{semana_s}-1", "%Y-%W-%w").date()
        
        # Verificar se a semana está entre o início do ano e a data atual
        if primeiro_dia_ano <= data_semana <= data:
            stock_liquido_total += dados["semanas"][semana][regiao][granularidade]["Stock Liquido"][periodo]
            count += 1
    
    # Se não houver dados, retornar 0
    if count == 0:
        return 0
    
    return stock_liquido_total / count

# Função para calcular COGS acumulado YTD
def calcular_cogs_acumulado_ytd(dados, data_atual, regiao, granularidade, periodo):
    # Converter data_atual para datetime
    if "W" in data_atual:  # Formato de semana
        ano, semana = data_atual.split("-W")
        data = datetime.strptime(f"{ano}-{semana}-1", "%Y-%W-%w").date()
    else:  # Formato de mês
        data = datetime.strptime(data_atual + "-01", "%Y-%m-%d").date()
    
    # Primeiro dia do ano
    primeiro_dia_ano = date(data.year, 1, 1)
    
    # Calcular COGS acumulado desde o início do ano até a data atual
    cogs_acumulado = 0
    
    # Para semanas
    for semana in dados["semanas"]:
        # Converter semana para data
        ano_s, semana_s = semana.split("-W")
        data_semana = datetime.strptime(f"{ano_s}-{semana_s}-1", "%Y-%W-%w").date()
        
        # Verificar se a semana está entre o início do ano e a data atual
        if primeiro_dia_ano <= data_semana <= data:
            cogs_acumulado += dados["semanas"][semana][regiao][granularidade]["COGS"][periodo]
    
    return cogs_acumulado

# Função para atualizar rotação
def atualizar_rotacao(dados):
    # Para cada semana
    for semana in dados["semanas"]:
        # Calcular dias acumulados para esta semana
        dias_acumulados = calcular_dias_acumulados(semana)
        
        # Para cada região
        for regiao in REGIOES_COM_IBERICA:
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Para EOP semanal: usar stock líquido médio daquela semana
                    stock_liquido_medio = dados["semanas"][semana][regiao][granularidade]["Stock Liquido"][periodo]
                    
                    # Calcular COGS acumulado YTD
                    cogs_acumulado = calcular_cogs_acumulado_ytd(dados, semana, regiao, granularidade, periodo)
                    
                    # Calcular rotação = (Stock Líquido médio / COGS acumulado) * Dias acumulados
                    dados["semanas"][semana][regiao][granularidade]["Rotação"][periodo] = calcular_rotacao(stock_liquido_medio, cogs_acumulado, dias_acumulados)
    
    # Para cada mês
    for mes in dados["meses"]:
        # Calcular dias acumulados para este mês
        dias_acumulados = calcular_dias_acumulados(mes)
        
        # Para cada região
        for regiao in REGIOES_COM_IBERICA:
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Para EOP mensal: usar stock líquido médio daquele mês
                    stock_liquido_medio = dados["meses"][mes][regiao][granularidade]["Stock Liquido"][periodo]
                    
                    # Calcular COGS acumulado YTD
                    cogs_acumulado = calcular_cogs_acumulado_ytd(dados, mes, regiao, granularidade, periodo)
                    
                    # Calcular rotação = (Stock Líquido médio / COGS acumulado) * Dias acumulados
                    dados["meses"][mes][regiao][granularidade]["Rotação"][periodo] = calcular_rotacao(stock_liquido_medio, cogs_acumulado, dias_acumulados)
                
                # Para cada período acumulado
                for periodo in PERIODOS_ANALISE:
                    # Para YTD: usar stock líquido médio desde o início do ano
                    stock_liquido_medio_ytd = calcular_stock_liquido_medio_ytd(dados, mes, regiao, granularidade, periodo)
                    
                    # Calcular COGS acumulado YTD
                    cogs_acumulado = calcular_cogs_acumulado_ytd(dados, mes, regiao, granularidade, periodo)
                    
                    # Calcular rotação YTD = (Stock Líquido médio YTD / COGS acumulado) * Dias acumulados
                    dados["meses"][mes][regiao][granularidade]["Rotação"]["YTD"][periodo] = calcular_rotacao(stock_liquido_medio_ytd, cogs_acumulado, dias_acumulados)
                    
                    # Para EOP: usar stock líquido médio do mês
                    dados["meses"][mes][regiao][granularidade]["Rotação"]["EOP"][periodo] = dados["meses"][mes][regiao][granularidade]["Rotação"][periodo]
    
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
        
        # Para cada região
        for regiao in REGIOES_COM_IBERICA:
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                # Para cada indicador
                for indicador in INDICADORES:
                    # Calcular média/soma das semanas para o mês
                    for periodo in PERIODOS_ANALISE:
                        valores = [dados["semanas"][s][regiao][granularidade][indicador][periodo] for s in semanas_do_mes]
                        if valores:
                            # Para vendas, MFO, quebra e COGS, somamos os valores
                            if indicador in ["Vendas", "MFO", "Quebra", "COGS"]:
                                dados["meses"][mes][regiao][granularidade][indicador][periodo] = sum(valores)
                            # Para stocks, calculamos a média
                            else:
                                dados["meses"][mes][regiao][granularidade][indicador][periodo] = sum(valores) / len(valores)
                    
                    # Atualizar YTD e EOP
                    for periodo in PERIODOS_ANALISE:
                        # EOP é o valor do final do período (último valor)
                        dados["meses"][mes][regiao][granularidade][indicador]["EOP"][periodo] = dados["meses"][mes][regiao][granularidade][indicador][periodo]
                        
                        # YTD é acumulado desde o início do ano
                        # Simplificação: usamos o mesmo valor para demonstração
                        dados["meses"][mes][regiao][granularidade][indicador]["YTD"][periodo] = dados["meses"][mes][regiao][granularidade][indicador][periodo]
    
    return dados

# Função para processar importação de dados CSV
def processar_importacao_csv(conteudo_csv):
    dados_importados = []
    csv_reader = csv.DictReader(io.StringIO(conteudo_csv))
    for row in csv_reader:
        dados_importados.append(row)
    return dados_importados

# Função para criar gráficos
def criar_grafico(dados, periodo_tipo, periodo, regiao, granularidade, indicador, periodos_analise):
    if periodo_tipo == "semanas":
        df = pd.DataFrame({
            "Período": list(dados["semanas"].keys()),
            **{p: [dados["semanas"][s][regiao][granularidade][indicador][p] for s in dados["semanas"]] for p in periodos_analise}
        })
    else:  # meses
        df = pd.DataFrame({
            "Período": list(dados["meses"].keys()),
            **{p: [dados["meses"][m][regiao][granularidade][indicador][p] for m in dados["meses"]] for p in periodos_analise}
        })
    
    fig = px.line(df, x="Período", y=periodos_analise, title=f"{indicador} - {regiao} - {granularidade}")
    fig.update_layout(height=400)
    return fig

# Função para criar gráficos de resumo mensal
def criar_grafico_resumo_mensal(dados, mes, regiao, granularidade, indicador, tipo_acumulado=None):
    if tipo_acumulado:
        df = pd.DataFrame({
            "Período": PERIODOS_ANALISE,
            "Valor": [dados["meses"][mes][regiao][granularidade][indicador][tipo_acumulado][p] for p in PERIODOS_ANALISE]
        })
        titulo = f"{indicador} - {regiao} - {granularidade} ({tipo_acumulado})"
    else:
        df = pd.DataFrame({
            "Período": PERIODOS_ANALISE,
            "Valor": [dados["meses"][mes][regiao][granularidade][indicador][p] for p in PERIODOS_ANALISE]
        })
        titulo = f"{indicador} - {regiao} - {granularidade}"
    
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

# Seleção de região (comum a todas as páginas)
regiao_selecionada = st.sidebar.selectbox("Selecione a Região:", REGIOES_COM_IBERICA)

if pagina == "Visão Semanal":
    st.header(f"Visão Semanal - {regiao_selecionada}")
    
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
        grafico = criar_grafico(dados, "semanas", semana_selecionada, regiao_selecionada, granularidade_selecionada, indicador_selecionado, periodos_selecionados)
        st.plotly_chart(grafico, use_container_width=True)
    
    # Exibir tabela de dados
    st.subheader(f"Dados da Semana {semana_selecionada} - {regiao_selecionada}")
    
    # Criar DataFrame para exibição
    dados_tabela = []
    for indicador in INDICADORES:
        linha = {"Indicador": indicador}
        for periodo in PERIODOS_ANALISE:
            linha[periodo] = dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada][indicador][periodo]
        dados_tabela.append(linha)
    
    df_tabela = pd.DataFrame(dados_tabela)
    st.dataframe(df_tabela, use_container_width=True)

elif pagina == "Resumo Mensal":
    st.header(f"Resumo Mensal - {regiao_selecionada}")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        mes_selecionado = st.selectbox("Selecione o Mês:", list(dados["meses"].keys()))
    with col2:
        granularidade_selecionada = st.selectbox("Selecione a Granularidade:", GRANULARIDADES_COM_TOTAL)
    with col3:
        tipo_acumulado = st.selectbox("Selecione o Tipo de Período:", ["Mensal", "YTD", "EOP"])
    
    # Exibir gráficos para cada indicador
    st.subheader(f"Resumo de {mes_selecionado} - {regiao_selecionada} - {granularidade_selecionada}")
    
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
                        grafico = criar_grafico_resumo_mensal(dados, mes_selecionado, regiao_selecionada, granularidade_selecionada, indicador)
                    else:
                        grafico = criar_grafico_resumo_mensal(dados, mes_selecionado, regiao_selecionada, granularidade_selecionada, indicador, tipo_acumulado)
                    st.plotly_chart(grafico, use_container_width=True)
    
    # Exibir tabela de dados
    st.subheader(f"Dados do Mês {mes_selecionado} - {regiao_selecionada}")
    
    # Criar DataFrame para exibição
    dados_tabela = []
    for indicador in INDICADORES:
        linha = {"Indicador": indicador}
        if tipo_acumulado == "Mensal":
            for periodo in PERIODOS_ANALISE:
                linha[periodo] = dados["meses"][mes_selecionado][regiao_selecionada][granularidade_selecionada][indicador][periodo]
        else:
            for periodo in PERIODOS_ANALISE:
                linha[periodo] = dados["meses"][mes_selecionado][regiao_selecionada][granularidade_selecionada][indicador][tipo_acumulado][periodo]
        dados_tabela.append(linha)
    
    df_tabela = pd.DataFrame(dados_tabela)
    st.dataframe(df_tabela, use_container_width=True)

elif pagina == "Introdução de Dados":
    st.header("Introdução de Dados para Simulação")
    
    # Verificar se a região selecionada é Ibérica
    if regiao_selecionada == "Ibérica":
        st.warning("A região Ibérica é calculada automaticamente como soma das regiões PT, ES Mainland e ES Canárias. Não é possível introduzir dados diretamente para esta região.")
    else:
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            semana_selecionada = st.selectbox("Selecione a Semana:", list(dados["semanas"].keys()))
            
            # Calcular e mostrar dias acumulados
            dias_acumulados = calcular_dias_acumulados(semana_selecionada)
            st.info(f"Dias acumulados desde o início do ano: {dias_acumulados} dias")
        
        with col2:
            granularidade_selecionada = st.selectbox("Selecione a Granularidade:", GRANULARIDADES)
            st.info("O Total é calculado automaticamente como soma das outras granularidades.")
        
        # Formulário para introdução de dados
        with st.form("formulario_dados"):
            st.subheader(f"Introduzir Dados para {semana_selecionada} - {regiao_selecionada} - {granularidade_selecionada}")
            
            # Criar campos para cada indicador
            valores = {}
            for indicador in INDICADORES:
                if indicador not in ["Rotação", "COGS"]:  # Rotação e COGS são calculados automaticamente
                    valores[indicador] = st.number_input(
                        f"{indicador} (Introduzido)", 
                        value=float(dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada][indicador]["Introduzido"]),
                        format="%.2f"
                    )
            
            # Botão de submissão
            submitted = st.form_submit_button("Salvar Dados")
            
            if submitted:
                # Atualizar dados
                for indicador, valor in valores.items():
                    dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada][indicador]["Introduzido"] = valor
                
                # Atualizar totais
                dados = atualizar_totais(dados)
                
                # Atualizar COGS
                dados = atualizar_cogs(dados)
                
                # Atualizar rotação
                dados = atualizar_rotacao(dados)
                
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
                linha[indicador] = dados["semanas"][semana_selecionada][regiao_selecionada][granularidade][indicador]["Introduzido"]
            dados_atuais.append(linha)
        
        df_atual = pd.DataFrame(dados_atuais)
        st.dataframe(df_atual, use_container_width=True)

elif pagina == "Importação de Dados":
    st.header("Importação Massiva de Dados")
    
    st.info("""
    Utilize esta página para importar dados em massa. 
    
    O arquivo CSV deve ter o seguinte formato:
    - Semana (formato: YYYY-WXX)
    - Região (PT, ES Mainland, ES Canárias)
    - Granularidade (Core, New Business, Services + Others, B2B)
    - Indicador (Stock Liquido, Stock Provision, Stock in Transit, Stock Bruto, Vendas, MFO, Quebra)
    - Período (Budget, Last Year, Real + Projeção, Introduzido)
    - Valor (número decimal)
    
    Exemplo:
    ```
    Semana,Região,Granularidade,Indicador,Periodo,Valor
    2025-W22,PT,Core,Stock Liquido,Introduzido,1000.5
    2025-W22,PT,Core,Vendas,Introduzido,500.25
    ```
    
    Nota: Os valores de COGS, Rotação, Total e Ibérica serão calculados automaticamente.
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
                    regiao = row.get("Região")
                    granularidade = row.get("Granularidade")
                    indicador = row.get("Indicador")
                    periodo = row.get("Periodo")
                    valor = float(row.get("Valor", 0))
                    
                    # Verificar se os valores são válidos
                    if (semana in dados["semanas"] and 
                        regiao in REGIOES and 
                        granularidade in GRANULARIDADES and 
                        indicador in INDICADORES and 
                        indicador not in ["Rotação", "COGS"] and 
                        periodo in PERIODOS_ANALISE):
                        
                        dados["semanas"][semana][regiao][granularidade][indicador][periodo] = valor
                
                # Atualizar totais
                dados = atualizar_totais(dados)
                
                # Atualizar COGS
                dados = atualizar_cogs(dados)
                
                # Atualizar rotação
                dados = atualizar_rotacao(dados)
                
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
        {"Semana": "2025-W22", "Região": "PT", "Granularidade": "Core", "Indicador": "Stock Liquido", "Periodo": "Introduzido", "Valor": "1000.5"},
        {"Semana": "2025-W22", "Região": "PT", "Granularidade": "Core", "Indicador": "Vendas", "Periodo": "Introduzido", "Valor": "500.25"},
        {"Semana": "2025-W22", "Região": "ES Mainland", "Granularidade": "Core", "Indicador": "Stock Liquido", "Periodo": "Introduzido", "Valor": "2000.5"},
        {"Semana": "2025-W22", "Região": "ES Mainland", "Granularidade": "Core", "Indicador": "Vendas", "Periodo": "Introduzido", "Valor": "1000.25"}
    ]
    
    df_template = pd.DataFrame(template_data)
    
    # Converter para CSV
    csv = df_template.to_csv(index=False)
    
    # Botão para download do template
    st.download_button(
        label="Download Template CSV",
        data=csv,
        file_name="template_importacao_v2.csv",
        mime="text/csv"
    )

# Rodapé
st.markdown("---")
st.markdown("Ferramenta de Monitorização de Stock © 2025")
