#!/bin/bash

# Define os cenários de teste
# Cada item é uma lista de heurísticas separadas por vírgula
SCENARIOS=("SA" "ILS" "BRKGA" "PSO" "SA,ILS" "BRKGA,PSO" "SA,ILS,BRKGA,PSO")
#SCENARIOS=("SA" "ILS")

# Local do arquivo de config
CONFIG_FILE="config/config_tests.conf"

# Função para gerar o arquivo de configuração para o cenário atual
gerar_config() {
    local ativos=$1
    # Cria o cabeçalho baseando-se no que está ativo
    {
		echo "# metaheuristics in the RKO, each line is executed in a separate thread"
        echo "$ativos" | tr ',' '\n'
        echo ""
        echo "# defines the maximum number of runs"
        echo "MAXRUNS 3"
		echo ""
        echo "# defines the execution mode (0 for test mode or 1 for debug mode)"
        echo "debug 0"
		echo ""
        echo "# defines the parameter configuration mode (0 for offline tuning, 1 for online configuration using Q-Learning)"
        echo "control 1"
		echo ""
        echo "# local search strategy (1 for first improvement, 2 for best improvement)"
        echo "strategy 1"
		echo ""
        echo "# strategy to restart the search process (percentage of the maximum time at which the restart is triggered)"
        echo "restart 1"
		echo ""
        echo "#size of the elite pool solution"
        echo "sizePool 10"
		echo ""
    } > "$CONFIG_FILE"
}

# --- Início do fluxo de experimentos ---
rm -rf ../Results
mkdir -p ../Results/logs ../Results/draws

make clean && make

TIME_LIMIT=10
BASES=("../Instances/2012caserta" "../Instances/2012zhu")

for SCENARIO in "${SCENARIOS[@]}"; do
    echo "Configurando experimento para: $SCENARIO"
    gerar_config "$SCENARIO"
	
    # Criar subpasta para organizar os resultados deste cenário específico
    FOLDER_NAME=$(echo "$SCENARIO" | tr ',' '-')
    mkdir -p "../Results/logs/$FOLDER_NAME"

    for BASE in "${BASES[@]}"; do
        [ -d "$BASE" ] || continue
        for dir in "$BASE"/*; do
            [ -d "$dir" ] || continue
            for inst in "$dir"/*; do
                [ -f "$inst" ] || continue

                NOME_ARQUIVO=$(basename "$inst")
                PASTA_PAI=$(basename "$dir")
                LOG_NOME="${FOLDER_NAME}/log-${PASTA_PAI}-${NOME_ARQUIVO}-${SCENARIO}"

                echo "Executando [$SCENARIO]: $NOME_ARQUIVO"
                ./runRKO "$inst" "$TIME_LIMIT" "$SCENARIO" > "../Results/logs/${LOG_NOME}" 2>&1
            done
        done
    done
done

# --- GERAÇÃO DOS PDFs ---
echo "====================================="
echo "Gerando PDFs das realocações..."
echo "====================================="

# Percorre todos os arquivos .txt gerados na pasta draws
for txt_file in ../Results/draws/draw-*; do
    # Verifica se o arquivo existe (previne erros se a pasta estiver vazia)
    [ -f "$txt_file" ] || continue
    
    # Extrai o nome base sem a extensão (ex: draw-instancia1)
    base_name=$(basename "$txt_file" .txt)
    
    # Define o caminho do PDF de saída
    pdf_out="../Results/draws/${base_name}.pdf"
    
    echo "Desenhando: $base_name"
    # Chama o Python passando o TXT de entrada e o PDF de saída
    python3 desenharSolucoes.py "$txt_file" "$pdf_out"
done

echo "Todos os PDFs foram gerados!"
