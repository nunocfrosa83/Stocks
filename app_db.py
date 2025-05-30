import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import sqlite3
from datetime import datetime, timedelta, date

# Constantes
REGIOES = ["PT", "ES Mainland", "ES Canárias"]
REGIOES_COM_IBERICA = REGIOES + ["Ibérica"]

GRANULARIDADES = ["Core", "New Business", "Services + Others", "B2B"]
GRANULARIDADES_COM_TOTAL = GRANULARIDADES + ["Total"]

INDICADORES = [
    "Rotação", 
    "Stock Liquido", 
    "Stock Provision", 
    "Stock in Transit", 
    "Stock Bruto", 
    "Vendas", 
    "MFO", 
    "Quebra", 
    "COGS"
]

PERIODOS_ANALISE = ["Budget", "Last Year", "Real + Projeção", "Introduzido"]

PERIODOS_ACUMULADOS = ["YTD", "EOP"]

# Caminho para o banco de dados
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_monitor.db')

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

# Função para conectar ao banco de dados
def conectar_bd():
    return sqlite3.connect(DB_PATH)

# Função para verificar se o banco de dados existe e está configurado
def verificar_bd():
    if not os.path.exists(DB_PATH):
        st.error("Banco de dados não encontrado. Executando configuração inicial...")
        from db_setup import criar_tabelas
        criar_tabelas()
        st.success("Banco de dados criado com sucesso!")
        return False
    return True

# Função para carregar dados do banco de dados
def carregar_dados_bd():
    if not verificar_bd():
        return criar_estrutura_dados()
    
    dados = {"semanas": {}, "meses": {}}
    conn = conectar_bd()
    
    try:
        # Carregar dados semanais
        df_semanas = pd.read_sql("""
            SELECT semana, regiao, granularidade, indicador, periodo, valor
            FROM dados_stock
            UNION ALL
            SELECT semana, regiao, granularidade, indicador, periodo, valor
            FROM view_iberica_semanal
            UNION ALL
            SELECT semana, regiao, granularidade, indicador, periodo, valor
            FROM view_total_semanal
        """, conn)
        
        # Processar dados semanais
        for _, row in df_semanas.iterrows():
            semana = row['semana']
            regiao = row['regiao']
            granularidade = row['granularidade']
            indicador = row['indicador']
            periodo = row['periodo']
            valor = row['valor']
            
            if semana not in dados["semanas"]:
                dados["semanas"][semana] = {}
            
            if regiao not in dados["semanas"][semana]:
                dados["semanas"][semana][regiao] = {}
            
            if granularidade not in dados["semanas"][semana][regiao]:
                dados["semanas"][semana][regiao][granularidade] = {}
            
            if indicador not in dados["semanas"][semana][regiao][granularidade]:
                dados["semanas"][semana][regiao][granularidade][indicador] = {}
            
            dados["semanas"][semana][regiao][granularidade][indicador][periodo] = valor
        
        # Carregar dados mensais
        df_meses = pd.read_sql("""
            SELECT mes, regiao, granularidade, indicador, periodo, periodo_acumulado, valor
            FROM dados_stock_mensal
        """, conn)
        
        # Processar dados mensais
        for _, row in df_meses.iterrows():
            mes = row['mes']
            regiao = row['regiao']
            granularidade = row['granularidade']
            indicador = row['indicador']
            periodo = row['periodo']
            periodo_acumulado = row['periodo_acumulado']
            valor = row['valor']
            
            if mes not in dados["meses"]:
                dados["meses"][mes] = {}
            
            if regiao not in dados["meses"][mes]:
                dados["meses"][mes][regiao] = {}
            
            if granularidade not in dados["meses"][mes][regiao]:
                dados["meses"][mes][regiao][granularidade] = {}
            
            if indicador not in dados["meses"][mes][regiao][granularidade]:
                dados["meses"][mes][regiao][granularidade][indicador] = {}
            
            if periodo_acumulado:
                if periodo_acumulado not in dados["meses"][mes][regiao][granularidade][indicador]:
                    dados["meses"][mes][regiao][granularidade][indicador][periodo_acumulado] = {}
                
                dados["meses"][mes][regiao][granularidade][indicador][periodo_acumulado][periodo] = valor
            else:
                dados["meses"][mes][regiao][granularidade][indicador][periodo] = valor
    
    except Exception as e:
        st.error(f"Erro ao carregar dados do banco de dados: {e}")
        return criar_estrutura_dados()
    
    finally:
        conn.close()
    
    # Atualizar cálculos automáticos
    dados = atualizar_cogs(dados)
    dados = atualizar_rotacao(dados)
    
    return dados

# Função para salvar dados no banco de dados
def salvar_dados_bd(dados, semana=None, regiao=None, granularidade=None, indicador=None, periodo=None, valor=None):
    if not verificar_bd():
        return False
    
    conn = conectar_bd()
    cursor = conn.cursor()
    
    try:
        if semana and regiao and granularidade and indicador and periodo is not None and valor is not None:
            # Inserir ou atualizar um valor específico
            cursor.execute("""
                INSERT INTO dados_stock (semana, regiao, granularidade, indicador, periodo, valor)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(semana, regiao, granularidade, indicador, periodo) 
                DO UPDATE SET valor = excluded.valor, data_atualizacao = CURRENT_TIMESTAMP
            """, (semana, regiao, granularidade, indicador, periodo, valor))
        else:
            # Salvar todos os dados (não implementado nesta versão)
            pass
        
        conn.commit()
        return True
    
    except Exception as e:
        st.error(f"Erro ao salvar dados no banco de dados: {e}")
        return False
    
    finally:
        conn.close()

# Função para criar estrutura de dados inicial
def criar_estrutura_dados():
    # Verificar se já existe um arquivo de dados
    if os.path.exists("dados.json"):
        try:
            with open("dados.json", "r") as f:
                return json.load(f)
        except:
            pass
    
    # Criar estrutura de dados vazia
    dados = {"semanas": {}, "meses": {}}
    
    # Gerar semanas para o ano atual
    ano_atual = datetime.now().year
    for semana in range(1, 53):
        semana_str = f"{ano_atual}-W{semana:02d}"
        dados["semanas"][semana_str] = {}
        
        for regiao in REGIOES_COM_IBERICA:
            dados["semanas"][semana_str][regiao] = {}
            
            for granularidade in GRANULARIDADES_COM_TOTAL:
                dados["semanas"][semana_str][regiao][granularidade] = {}
                
                for indicador in INDICADORES:
                    dados["semanas"][semana_str][regiao][granularidade][indicador] = {}
                    
                    for periodo in PERIODOS_ANALISE:
                        dados["semanas"][semana_str][regiao][granularidade][indicador][periodo] = 0.0
    
    # Gerar meses para o ano atual
    for mes in range(1, 13):
        mes_str = f"{ano_atual}-{mes:02d}"
        dados["meses"][mes_str] = {}
        
        for regiao in REGIOES_COM_IBERICA:
            dados["meses"][mes_str][regiao] = {}
            
            for granularidade in GRANULARIDADES_COM_TOTAL:
                dados["meses"][mes_str][regiao][granularidade] = {}
                
                for indicador in INDICADORES:
                    dados["meses"][mes_str][regiao][granularidade][indicador] = {}
                    
                    for periodo in PERIODOS_ANALISE:
                        dados["meses"][mes_str][regiao][granularidade][indicador][periodo] = 0.0
                    
                    for periodo_acumulado in PERIODOS_ACUMULADOS:
                        dados["meses"][mes_str][regiao][granularidade][indicador][periodo_acumulado] = {}
                        
                        for periodo in PERIODOS_ANALISE:
                            dados["meses"][mes_str][regiao][granularidade][indicador][periodo_acumulado][periodo] = 0.0
    
    return dados

# Função para calcular COGS
def calcular_cogs(vendas, mfo, quebra):
    return vendas - mfo - quebra

# Função para calcular rotação
def calcular_rotacao(stock_liquido_medio, cogs_acumulado, dias_acumulados):
    if stock_liquido_medio == 0 or cogs_acumulado == 0:
        return 0
    return (stock_liquido_medio / cogs_acumulado) * dias_acumulados

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
                    # Obter valores
                    vendas = dados["semanas"][semana][regiao][granularidade]["Vendas"][periodo]
                    mfo = dados["semanas"][semana][regiao][granularidade]["MFO"][periodo]
                    quebra = dados["semanas"][semana][regiao][granularidade]["Quebra"][periodo]
                    
                    # Calcular COGS
                    dados["semanas"][semana][regiao][granularidade]["COGS"][periodo] = calcular_cogs(vendas, mfo, quebra)
    
    # Para cada mês
    for mes in dados["meses"]:
        # Para cada região
        for regiao in REGIOES_COM_IBERICA:
            # Para cada granularidade
            for granularidade in GRANULARIDADES_COM_TOTAL:
                # Para cada período
                for periodo in PERIODOS_ANALISE:
                    # Obter valores
                    vendas = dados["meses"][mes][regiao][granularidade]["Vendas"][periodo]
                    mfo = dados["meses"][mes][regiao][granularidade]["MFO"][periodo]
                    quebra = dados["meses"][mes][regiao][granularidade]["Quebra"][periodo]
                    
                    # Calcular COGS
                    dados["meses"][mes][regiao][granularidade]["COGS"][periodo] = calcular_cogs(vendas, mfo, quebra)
                
                # Para cada período acumulado
                for periodo_acumulado in PERIODOS_ACUMULADOS:
                    for periodo in PERIODOS_ANALISE:
                        # Obter valores
                        vendas = dados["meses"][mes][regiao][granularidade]["Vendas"][periodo_acumulado][periodo]
                        mfo = dados["meses"][mes][regiao][granularidade]["MFO"][periodo_acumulado][periodo]
                        quebra = dados["meses"][mes][regiao][granularidade]["Quebra"][periodo_acumulado][periodo]
                        
                        # Calcular COGS
                        dados["meses"][mes][regiao][granularidade]["COGS"][periodo_acumulado][periodo] = calcular_cogs(vendas, mfo, quebra)
    
    return dados

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

# Função para obter histórico de alterações
def obter_historico_alteracoes(limite=100):
    if not verificar_bd():
        return []
    
    conn = conectar_bd()
    
    try:
        df = pd.read_sql(f"""
            SELECT 
                id,
                tabela,
                semana_ou_mes,
                regiao,
                granularidade,
                indicador,
                periodo,
                periodo_acumulado,
                valor_antigo,
                valor_novo,
                usuario,
                datetime(data_alteracao) as data_alteracao
            FROM 
                historico_alteracoes
            ORDER BY 
                data_alteracao DESC
            LIMIT {limite}
        """, conn)
        
        return df
    
    except Exception as e:
        st.error(f"Erro ao obter histórico de alterações: {e}")
        return []
    
    finally:
        conn.close()

# Configuração da página
st.set_page_config(
    page_title="Ferramenta de Monitorização de Stock",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Carregar dados
dados = carregar_dados_bd()

# Sidebar
st.sidebar.title("Ferramenta de Monitorização de Stock")

# Seleção de região
regiao_selecionada = st.sidebar.selectbox("Selecione a Região:", REGIOES_COM_IBERICA)

# Seleção de página
pagina = st.sidebar.radio("Selecione a Página:", ["Visão Semanal", "Resumo Mensal", "Introdução de Dados", "Histórico de Alterações"])

# Visão Semanal
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
    
    # Seleção de períodos para comparação
    periodos_selecionados = st.multiselect("Selecione os Períodos para Comparação:", PERIODOS_ANALISE, default=PERIODOS_ANALISE)
    
    if periodos_selecionados:
        # Preparar dados para o gráfico
        valores = []
        for periodo in periodos_selecionados:
            valor = dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada][indicador_selecionado][periodo]
            valores.append({"Período": periodo, "Valor": valor})
        
        df = pd.DataFrame(valores)
        
        # Criar gráfico
        fig = px.bar(
            df, 
            x="Período", 
            y="Valor", 
            title=f"{indicador_selecionado} - {semana_selecionada} - {regiao_selecionada} - {granularidade_selecionada}",
            color="Período"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabela de dados
        st.subheader("Dados Detalhados")
        st.dataframe(df)
    else:
        st.warning("Selecione pelo menos um período para visualização.")

# Resumo Mensal
elif pagina == "Resumo Mensal":
    st.header(f"Resumo Mensal - {regiao_selecionada}")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        mes_selecionado = st.selectbox("Selecione o Mês:", list(dados["meses"].keys()))
    
    with col2:
        granularidade_selecionada = st.selectbox("Selecione a Granularidade:", GRANULARIDADES_COM_TOTAL)
    
    with col3:
        tipo_periodo = st.selectbox("Selecione o Tipo de Período:", ["Mensal", "YTD", "EOP"])
    
    # Preparar dados para os gráficos
    dados_tabela = []
    
    for indicador in INDICADORES:
        for periodo in PERIODOS_ANALISE:
            if tipo_periodo == "Mensal":
                valor = dados["meses"][mes_selecionado][regiao_selecionada][granularidade_selecionada][indicador][periodo]
            else:  # YTD ou EOP
                valor = dados["meses"][mes_selecionado][regiao_selecionada][granularidade_selecionada][indicador][tipo_periodo][periodo]
            
            dados_tabela.append({
                "Indicador": indicador,
                "Período": periodo,
                "Valor": valor
            })
    
    df_tabela = pd.DataFrame(dados_tabela)
    
    # Criar gráficos para cada indicador
    st.subheader(f"Gráficos - {tipo_periodo}")
    
    # Organizar gráficos em colunas
    col1, col2 = st.columns(2)
    
    for i, indicador in enumerate(INDICADORES):
        df_indicador = df_tabela[df_tabela["Indicador"] == indicador]
        
        fig = px.bar(
            df_indicador, 
            x="Período", 
            y="Valor", 
            title=f"{indicador}",
            color="Período"
        )
        
        if i % 2 == 0:
            with col1:
                st.plotly_chart(fig, use_container_width=True)
        else:
            with col2:
                st.plotly_chart(fig, use_container_width=True)
    
    # Tabela de dados
    st.subheader("Dados Detalhados")
    
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
            
            # Criar campos para cada indicador (exceto COGS e Rotação que são calculados)
            valores = {}
            for indicador in INDICADORES:
                if indicador not in ["COGS", "Rotação"]:
                    valores[indicador] = {}
                    st.subheader(indicador)
                    
                    for periodo in PERIODOS_ANALISE:
                        valor_atual = dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada][indicador][periodo]
                        valores[indicador][periodo] = st.number_input(
                            f"{periodo}", 
                            value=float(valor_atual),
                            format="%.2f",
                            key=f"{indicador}_{periodo}"
                        )
            
            # Botão para salvar
            submitted = st.form_submit_button("Salvar Dados")
            
            if submitted:
                # Salvar os dados introduzidos
                for indicador in valores:
                    for periodo in valores[indicador]:
                        valor = valores[indicador][periodo]
                        
                        # Salvar no banco de dados
                        sucesso = salvar_dados_bd(
                            dados,
                            semana=semana_selecionada,
                            regiao=regiao_selecionada,
                            granularidade=granularidade_selecionada,
                            indicador=indicador,
                            periodo=periodo,
                            valor=valor
                        )
                        
                        if sucesso:
                            # Atualizar dados em memória
                            dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada][indicador][periodo] = valor
                
                # Recalcular COGS e Rotação
                dados = atualizar_cogs(dados)
                dados = atualizar_rotacao(dados)
                
                st.success("Dados salvos com sucesso!")
                
                # Mostrar valores calculados
                st.subheader("Valores Calculados")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("COGS")
                    for periodo in PERIODOS_ANALISE:
                        valor = dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada]["COGS"][periodo]
                        st.metric(f"{periodo}", f"{valor:.2f}")
                
                with col2:
                    st.subheader("Rotação")
                    for periodo in PERIODOS_ANALISE:
                        valor = dados["semanas"][semana_selecionada][regiao_selecionada][granularidade_selecionada]["Rotação"][periodo]
                        st.metric(f"{periodo}", f"{valor:.2f}")

elif pagina == "Histórico de Alterações":
    st.header("Histórico de Alterações")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        limite = st.slider("Número de registros a exibir:", 10, 500, 100)
    
    # Obter histórico
    historico = obter_historico_alteracoes(limite)
    
    if len(historico) > 0:
        # Exibir histórico
        st.dataframe(historico, use_container_width=True)
    else:
        st.info("Nenhuma alteração registrada ainda.")
