import pandas as pd
import numpy as np
import logging
import unicodedata
from pathlib import Path
import sys

# Configuração de log para acompanhamento no terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def remover_acentos(texto: str) -> str:
    """Remove acentos de uma string para facilitar a busca dinâmica."""
    try:
        texto = str(texto)
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    except Exception:
        return texto

def encontrar_arquivo_dinamicamente(pasta: Path, prefixo: str) -> Path:
    """Busca um arquivo na pasta baseada no prefixo (aceita Excel e CSV)."""
    prefixo_limpo = remover_acentos(prefixo).lower().strip()
    todos_arquivos = [f for f in pasta.iterdir() if f.is_file()]
    arquivos_encontrados = []
    
    for f in todos_arquivos:
        if f.suffix.lower() in ['.xlsx', '.xls', '.xlsm', '.xlsb', '.csv']:
            nome_limpo = remover_acentos(f.name).lower()
            if prefixo_limpo in nome_limpo:
                arquivos_encontrados.append(f)
                
    if not arquivos_encontrados:
        arquivos_na_pasta = [f.name for f in todos_arquivos]
        erro_msg = (
            f"\nNenhum arquivo contendo o prefixo '{prefixo}' foi encontrado na pasta:\n"
            f"{pasta}\n\n"
            f"ARQUIVOS DISPONÍVEIS NESTA PASTA:\n{arquivos_na_pasta}\n"
        )
        logging.error(erro_msg)
        raise FileNotFoundError(f"Arquivo '{prefixo}' não encontrado.")
        
    arquivo_alvo = arquivos_encontrados[0]
    logging.info(f"Arquivo '{prefixo}' localizado: {arquivo_alvo.name}")
    return arquivo_alvo

def carregar_arquivo(caminho: Path) -> pd.DataFrame:
    """Carrega o arquivo identificando automaticamente se é Excel ou CSV."""
    try:
        if caminho.suffix.lower() == '.csv':
            logging.info(f"Lendo CSV: {caminho.name}...")
            try:
                df = pd.read_csv(caminho, sep=';', encoding='latin1')
                if len(df.columns) <= 1:
                    df = pd.read_csv(caminho, sep=',', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(caminho, sep=',', encoding='utf-8')
            return df
        else:
            logging.info(f"Lendo Excel: {caminho.name}...")
            df = pd.read_excel(caminho)
            return df
    except Exception as e:
        logging.error(f"Erro ao ler {caminho.name}: {e}")
        raise

def padronizar_chave(df: pd.DataFrame, nome_coluna: str) -> pd.DataFrame:
    """Limpa a chave de cruzamento (remove '.0', espaços e converte para string)."""
    df_clean = df.copy()
    if nome_coluna not in df_clean.columns:
        raise ValueError(f"A coluna '{nome_coluna}' não foi encontrada no arquivo.")
        
    df_clean[nome_coluna] = (
        df_clean[nome_coluna]
        .astype(str)
        .str.replace(r'\.0$', '', regex=True)
        .str.strip()
        .str.upper()
    )
    df_clean[nome_coluna] = df_clean[nome_coluna].replace(['NAN', 'NONE', 'NULL', ''], np.nan)
    return df_clean

def transpor_assuntos(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma múltiplas linhas de assuntos do mesmo ticket em colunas."""
    logging.info("Agrupando tickets duplicados e transpondo os assuntos...")
    
    if 'ticket_id' not in df.columns or 'assunto' not in df.columns:
        logging.warning("Colunas 'ticket_id' ou 'assunto' não encontradas. Pulando transposição.")
        return df.drop_duplicates(subset=['ticket_id'], keep='first') if 'ticket_id' in df.columns else df

    df_validos = df.dropna(subset=['ticket_id', 'assunto'])
    if df_validos.empty:
        return df.drop_duplicates(subset=['ticket_id'], keep='first')

    assuntos_por_ticket = df_validos.groupby('ticket_id')['assunto'].apply(list).reset_index()
    
    assuntos_expandidos = pd.DataFrame(assuntos_por_ticket['assunto'].to_list())
    num_colunas = assuntos_expandidos.shape[1]
    
    nomes_colunas = ['assunto'] + [f'Assunto {i+2}' for i in range(1, num_colunas)]
    assuntos_expandidos.columns = nomes_colunas
    assuntos_expandidos['ticket_id'] = assuntos_por_ticket['ticket_id']
    
    df_base_unica = df.drop(columns=['assunto']).drop_duplicates(subset=['ticket_id'], keep='first')
    
    df_final = pd.merge(df_base_unica, assuntos_expandidos, on='ticket_id', how='left')
    
    logging.info(f"Tickets deduplicados. Máximo de colunas de assunto geradas: {num_colunas}")
    return df_final

def main():
    # 1. RESOLUÇÃO DINÂMICA DE DIRETÓRIOS (À Prova de Subpastas)
    diretorio_atual = Path(__file__).resolve().parent
    
    # O script procura pela pasta '01_raw' subindo os níveis de pasta automaticamente
    base_dir = diretorio_atual
    for parent in [diretorio_atual] + list(diretorio_atual.parents):
        if (parent / "01_raw").exists():
            base_dir = parent
            break
            
    pasta_raw = base_dir / "01_raw"
    pasta_silver = base_dir / "02_silver"
    caminho_saida = pasta_silver / "BASE_GERAL_PRE_CONTENCIOSO.xlsx"
    
    if not pasta_raw.exists():
        logging.error(f"A pasta de origem não foi encontrada em nenhum nível acima de: {diretorio_atual}")
        logging.error("Certifique-se de que a pasta '01_raw' existe no projeto.")
        sys.exit(1)
        
    pasta_silver.mkdir(parents=True, exist_ok=True)

    try:
        # 2. COLETA DINÂMICA (Ajustada para os novos diretórios)
        logging.info("Buscando arquivos necessários...")
        
        # Analytics agora vem da pasta 02_silver com o novo prefixo
        arquivo_analytics_path = encontrar_arquivo_dinamicamente(pasta_silver, "ANALYTICS_BASE_TICKETS_processed")
        
        # Cadastro continua vindo da pasta 01_raw
        arquivo_cadastro_path = encontrar_arquivo_dinamicamente(pasta_raw, "Base_Cadastro")
        
        # 3. Carregar Dados
        df_analytics = carregar_arquivo(arquivo_analytics_path)
        df_cadastro = carregar_arquivo(arquivo_cadastro_path)
        
        # 4. Limpeza das Chaves
        logging.info("Padronizando as chaves (matricula e NUM_LIGACAO)...")
        df_analytics = padronizar_chave(df_analytics, 'matricula')
        df_cadastro = padronizar_chave(df_cadastro, 'NUM_LIGACAO')
        
        # 5. Deduplicar Cadastro
        logging.info("Garantindo unicidade na Base de Cadastro...")
        df_cadastro_unico = df_cadastro.drop_duplicates(subset=['NUM_LIGACAO'], keep='first').copy()
        
        # 6. Cruzamento (Left Join)
        logging.info("Cruzando Analytics com Cadastro...")
        df_merged = pd.merge(
            df_analytics,
            df_cadastro_unico,
            left_on='matricula',
            right_on='NUM_LIGACAO',
            how='left'
        )
        
        # 7. Pivotamento dos Assuntos
        df_final = transpor_assuntos(df_merged)
        
        # 8. Reorganização visual das colunas
        colunas_assunto = [col for col in df_final.columns if col.startswith('Assunto ')]
        colunas_ordenadas = list(df_final.columns)
        
        if 'ticket_id' in colunas_ordenadas and 'assunto' in colunas_ordenadas:
            idx_ticket = colunas_ordenadas.index('ticket_id')
            colunas_ordenadas.remove('assunto')
            for col in colunas_assunto:
                colunas_ordenadas.remove(col)
                
            inserir_em = idx_ticket + 1
            for col in reversed(['assunto'] + colunas_assunto):
                colunas_ordenadas.insert(inserir_em, col)
            
            df_final = df_final[colunas_ordenadas]
        
        # 9. Salvar Arquivo
        logging.info("Salvando o relatório final na pasta 02_silver...")
        df_final.to_excel(caminho_saida, index=False)
        logging.info(f"SUCESSO! Relatório disponível em: {caminho_saida}")
        
    except Exception as e:
        logging.error(f"A execução foi interrompida: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()