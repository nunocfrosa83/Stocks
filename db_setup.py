import sqlite3
import os
import json
from datetime import datetime, timedelta, date
import sys

# Caminho para o banco de dados
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_monitor.db')

def criar_tabelas():
    """Cria as tabelas no banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela dados_stock
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dados_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        semana TEXT NOT NULL,
        regiao TEXT NOT NULL,
        granularidade TEXT NOT NULL,
        indicador TEXT NOT NULL,
        periodo TEXT NOT NULL,
        valor REAL NOT NULL,
        origem TEXT DEFAULT 'manual',
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(semana, regiao, granularidade, indicador, periodo)
    )
    ''')
    
    # Tabela dados_stock_mensal
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dados_stock_mensal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes TEXT NOT NULL,
        regiao TEXT NOT NULL,
        granularidade TEXT NOT NULL,
        indicador TEXT NOT NULL,
        periodo TEXT NOT NULL,
        periodo_acumulado TEXT,
        valor REAL NOT NULL,
        calculado BOOLEAN DEFAULT 1,
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(mes, regiao, granularidade, indicador, periodo, periodo_acumulado)
    )
    ''')
    
    # Tabela historico_alteracoes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS historico_alteracoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tabela TEXT NOT NULL,
        id_registro INTEGER NOT NULL,
        semana_ou_mes TEXT NOT NULL,
        regiao TEXT NOT NULL,
        granularidade TEXT NOT NULL,
        indicador TEXT NOT NULL,
        periodo TEXT NOT NULL,
        periodo_acumulado TEXT,
        valor_antigo REAL,
        valor_novo REAL,
        usuario TEXT DEFAULT 'sistema',
        data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabela usuarios (para fase futura)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        ativo BOOLEAN DEFAULT 1,
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ultimo_acesso TIMESTAMP
    )
    ''')
    
    # Tabela configuracao_excel (para fase futura)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS configuracao_excel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sharepoint_url TEXT,
        caminho_arquivo TEXT,
        nome_arquivo TEXT,
        planilha TEXT,
        intervalo_celulas TEXT,
        mapeamento_colunas TEXT,
        ultima_sincronizacao TIMESTAMP,
        intervalo_sincronizacao INTEGER DEFAULT 604800,
        ativo BOOLEAN DEFAULT 1
    )
    ''')
    
    # Criar índices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dados_stock_semana ON dados_stock(semana)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dados_stock_regiao ON dados_stock(regiao)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dados_stock_indicador ON dados_stock(indicador)')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dados_stock_mensal_mes ON dados_stock_mensal(mes)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dados_stock_mensal_regiao ON dados_stock_mensal(regiao)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dados_stock_mensal_indicador ON dados_stock_mensal(indicador)')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_historico_alteracoes_data ON historico_alteracoes(data_alteracao)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_historico_alteracoes_usuario ON historico_alteracoes(usuario)')
    
    # Criar trigger para histórico de alterações
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS tr_dados_stock_alterados
    AFTER UPDATE ON dados_stock
    FOR EACH ROW
    BEGIN
        INSERT INTO historico_alteracoes (
            tabela, id_registro, semana_ou_mes, regiao, granularidade, 
            indicador, periodo, valor_antigo, valor_novo
        ) VALUES (
            'dados_stock', NEW.id, NEW.semana, NEW.regiao, NEW.granularidade,
            NEW.indicador, NEW.periodo, OLD.valor, NEW.valor
        );
    END;
    ''')
    
    # Criar views
    # View para Região Ibérica
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS view_iberica_semanal AS
    SELECT 
        semana,
        'Ibérica' AS regiao,
        granularidade,
        indicador,
        periodo,
        SUM(valor) AS valor,
        'calculado' AS origem,
        MAX(data_atualizacao) AS data_atualizacao
    FROM 
        dados_stock
    WHERE 
        regiao IN ('PT', 'ES Mainland', 'ES Canárias')
    GROUP BY 
        semana, granularidade, indicador, periodo
    ''')
    
    # View para Granularidade Total
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS view_total_semanal AS
    SELECT 
        semana,
        regiao,
        'Total' AS granularidade,
        indicador,
        periodo,
        SUM(valor) AS valor,
        'calculado' AS origem,
        MAX(data_atualizacao) AS data_atualizacao
    FROM 
        dados_stock
    WHERE 
        granularidade IN ('Core', 'New Business', 'Services + Others', 'B2B')
    GROUP BY 
        semana, regiao, indicador, periodo
    ''')
    
    conn.commit()
    conn.close()
    
    print("Tabelas, índices, triggers e views criados com sucesso!")

def migrar_dados_json_para_sqlite(json_path):
    """Migra os dados do arquivo JSON para o banco de dados SQLite."""
    if not os.path.exists(json_path):
        print(f"Arquivo JSON não encontrado: {json_path}")
        return False
    
    try:
        with open(json_path, 'r') as f:
            dados = json.load(f)
    except Exception as e:
        print(f"Erro ao ler arquivo JSON: {e}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Migrar dados semanais
    for semana, dados_semana in dados.get("semanas", {}).items():
        for regiao, dados_regiao in dados_semana.items():
            if regiao == "Ibérica":
                continue  # Ibérica é calculada automaticamente via view
            
            for granularidade, dados_granularidade in dados_regiao.items():
                if granularidade == "Total":
                    continue  # Total é calculado automaticamente via view
                
                for indicador, dados_indicador in dados_granularidade.items():
                    for periodo, valor in dados_indicador.items():
                        if isinstance(valor, dict):
                            # Pular valores aninhados (como períodos acumulados)
                            continue
                        
                        if isinstance(valor, (int, float)):
                            try:
                                cursor.execute('''
                                INSERT INTO dados_stock (semana, regiao, granularidade, indicador, periodo, valor, origem)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(semana, regiao, granularidade, indicador, periodo) 
                                DO UPDATE SET valor = excluded.valor, data_atualizacao = CURRENT_TIMESTAMP
                                ''', (semana, regiao, granularidade, indicador, periodo, valor, 'migrado'))
                            except Exception as e:
                                print(f"Erro ao inserir dado semanal: {e}")
                                print(f"Dados: {semana}, {regiao}, {granularidade}, {indicador}, {periodo}, {valor}")
    
    # Migrar dados mensais
    for mes, dados_mes in dados.get("meses", {}).items():
        for regiao, dados_regiao in dados_mes.items():
            if regiao == "Ibérica":
                continue  # Ibérica é calculada automaticamente
            
            for granularidade, dados_granularidade in dados_regiao.items():
                if granularidade == "Total":
                    continue  # Total é calculado automaticamente
                
                for indicador, dados_indicador in dados_granularidade.items():
                    for periodo, valor in dados_indicador.items():
                        if isinstance(valor, dict):
                            # Processar períodos acumulados (YTD, EOP)
                            for periodo_acumulado, valor_acumulado in valor.items():
                                if isinstance(valor_acumulado, (int, float)):
                                    try:
                                        cursor.execute('''
                                        INSERT INTO dados_stock_mensal (mes, regiao, granularidade, indicador, periodo, periodo_acumulado, valor)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                        ON CONFLICT(mes, regiao, granularidade, indicador, periodo, periodo_acumulado) 
                                        DO UPDATE SET valor = excluded.valor, data_atualizacao = CURRENT_TIMESTAMP
                                        ''', (mes, regiao, granularidade, indicador, periodo, periodo_acumulado, valor_acumulado))
                                    except Exception as e:
                                        print(f"Erro ao inserir dado mensal acumulado: {e}")
                        elif isinstance(valor, (int, float)):
                            try:
                                cursor.execute('''
                                INSERT INTO dados_stock_mensal (mes, regiao, granularidade, indicador, periodo, valor)
                                VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT(mes, regiao, granularidade, indicador, periodo, periodo_acumulado) 
                                DO UPDATE SET valor = excluded.valor, data_atualizacao = CURRENT_TIMESTAMP
                                ''', (mes, regiao, granularidade, indicador, periodo, valor))
                            except Exception as e:
                                print(f"Erro ao inserir dado mensal: {e}")
    
    conn.commit()
    conn.close()
    
    print("Migração de dados concluída com sucesso!")
    return True

def adicionar_usuario_padrao():
    """Adiciona um usuário padrão para testes."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Senha padrão: admin123
    cursor.execute('''
    INSERT OR IGNORE INTO usuarios (nome, email, senha_hash)
    VALUES (?, ?, ?)
    ''', ('Administrador', 'admin@exemplo.com', 'pbkdf2:sha256:150000$abc123$abcdef1234567890abcdef1234567890'))
    
    conn.commit()
    conn.close()
    
    print("Usuário padrão adicionado com sucesso!")

if __name__ == "__main__":
    print("Iniciando configuração do banco de dados...")
    
    # Verificar se o banco de dados já existe
    db_exists = os.path.exists(DB_PATH)
    
    # Criar tabelas
    criar_tabelas()
    
    # Se for uma nova instalação, adicionar usuário padrão
    if not db_exists:
        adicionar_usuario_padrao()
    
    # Verificar se foi fornecido um caminho para o arquivo JSON
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        print(f"Migrando dados do arquivo: {json_path}")
        migrar_dados_json_para_sqlite(json_path)
    else:
        print("Nenhum arquivo JSON fornecido para migração.")
    
    print("Configuração do banco de dados concluída!")
