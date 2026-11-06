// *******************************************************************
//	  file with specific functions to solve the Unloading Block Relocation Problem
// *******************************************************************
#ifndef _PROBLEM_H
#define _PROBLEM_H

#include <filesystem> // Necessário compilar com C++17 ou superior (ex: -std=c++2a)
#include <functional> 
#include <fstream>
#include <string>

//----------------- DEFINITION OF PROBLEM SPECIFIC TYPES -----------------------

// Estrutura contendo os dados da instancia do problema (UBRP)
struct TProblemData {
	int n; // Tamanho do vetor RKO (geralmente igual a numberOfBlocks)
	
	std::vector<std::vector<int>> stacks;
	int numberOfStacks = 0; 	// Quantidade total de pilhas na baia
	int numberOfBlocks = 0; 	// Quantidade total de blocos
	int stackHeight	= 0; 		// Altura maxima permitida para as pilhas
};


//-------------------------- FUNCTIONS OF SPECIFIC PROBLEM --------------------------


/**************************************************************************
 Method: ReadData
 Description: Le e estrutura os dados de entrada do problema a partir do .txt
**************************************************************************/
void ReadData(char name[], TProblemData &data)
{ 
	const std::string filepath = name;
	std::ifstream file(filepath);

	if (!file.is_open()) {
		std::cerr << "Erro: Nao foi possivel abrir o arquivo " << filepath << std::endl;
        exit(1);
	}

	std::string line;

	// 1. Le a primeira linha: numero de pilhas e numero total de blocos
	std::getline(file, line);
	{
		std::istringstream ss(line);
		ss >> data.numberOfStacks >> data.numberOfBlocks;
	}

	// 2. Processa as linhas restantes (pilhas iniciais)
	while (std::getline(file, line)) {
		if (line.empty()) continue;
		
		std::istringstream ss(line);
		int cnt; 
		ss >> cnt; 
		
		std::vector<int> stack;
		stack.reserve(cnt); // Otimizacao de alocacao
		
		int v;
		while (ss >> v) {
			stack.push_back(v);
		}
		
		if ((int)stack.size() != cnt) {
			throw std::runtime_error("Tamanho da pilha inconsistente em " + filepath);
		}
		
		data.stacks.push_back(std::move(stack));
	}

	// 3. Verificacoes de integridade da instancia
	if ((int)data.stacks.size() != data.numberOfStacks) {
		throw std::runtime_error("Numero incorreto de pilhas em " + filepath);
	}

	int total = 0;
	for (const auto& s : data.stacks) {
		total += (int)s.size();
	}
	
	if (total != data.numberOfBlocks) {
		throw std::runtime_error("Inconsistencia na contagem total de blocos em " + filepath);
	}

	// 4. Infere a altura maxima (H)
	namespace fs = std::filesystem;
	std::string folder = fs::path(filepath).parent_path().filename().string();
	std::string parent_folder = fs::path(filepath).parent_path().parent_path().filename().string();
	
	if (parent_folder == "2012zhu") {
		// Para 2012zhu: extrai o primeiro número do nome da pasta (ex: "7-10-63")
		try {
			data.stackHeight = std::stoi(folder.substr(0, folder.find('-')));
		} catch (...) {
			data.stackHeight = 10; // Valor de segurança ou fallback
		}
	} else{
		// Para 2012caserta e outros datasets: lógica fixa
		data.stackHeight = data.numberOfBlocks / data.numberOfStacks + 2;
	} 
	
	// Define o tamanho do vetor RKO
	data.n = data.numberOfBlocks; 

	// TRAVA DE SEGURANÇA:
	if (data.n <= 0 || data.numberOfStacks <= 0) {
		throw std::runtime_error("Erro: Instancia sem blocos ou pilhas (arquivo possivelmente vazio ou invalido): " + filepath);
	}
}

// ========================================================================
// ARQUITETURA HEURISTICA (REGRAS)
// ========================================================================

// Assinatura padrao de qualquer regra heuristica
using RuleFunction = std::function<int(int b, 
									   const std::vector<int>& candidates, 
									   const std::vector<std::vector<int>>& stacks, 
									   int max_H, 
									   int next_target)>;

// Regra 1: Minimizar Bloqueios (Preservacao Estrutural)
inline int RuleMinimizarBloqueios(int b, const std::vector<int>& candidates, const std::vector<std::vector<int>>& stacks, int max_H, int next_target) {
	int best_d = candidates[0];
	double best_score = 1e9;
	for (int c : candidates) {
		double score = (!stacks[c].empty() && stacks[c].back() < b) ? 1.0 : 0.0;
		score += 0.5 * ((double)stacks[c].size() / max_H); 
		if (score < best_score) { best_score = score; best_d = c; }
	}
	return best_d;
}

// Regra 2: Menos Carregada (Balanceamento de Carga)
inline int RuleMenosCarregada(int b, const std::vector<int>& candidates, const std::vector<std::vector<int>>& stacks, int max_H, int next_target) {
	int best_d = candidates[0];
	for (int c : candidates) if (stacks[c].size() < stacks[best_d].size()) best_d = c;
	return best_d;
}

// Regra 3: Mais Carregada Viavel (Concentracao)
inline int RuleMaisCarregadaViavel(int b, const std::vector<int>& candidates, const std::vector<std::vector<int>>& stacks, int max_H, int next_target) {
	int best_d = candidates[0];
	for (int c : candidates) if (stacks[c].size() > stacks[best_d].size()) best_d = c;
	return best_d;
}

// Regra 4: Min-Max (Encaixe Perfeito - Busca não criar bloqueios futuros)
inline int RuleMinMax(int b, const std::vector<int>& candidates, const std::vector<std::vector<int>>& stacks, int max_H, int next_target) {
	int best_d = candidates[0];
	int best_diff = 1e9; 

	for (int c : candidates) {
		if (stacks[c].empty()) continue; 
		
		int diff = stacks[c].back() - b;
		
		// Menor diferenca positiva
		if (diff > 0 && diff < best_diff) {
			best_diff = diff;
			best_d = c;
		}
	}
	return best_d;
}

// Regra 5: Look-Ahead (Fuga do proximo alvo para evitar retrabalho imediato)
inline int RuleLookAhead(int b, const std::vector<int>& candidates, const std::vector<std::vector<int>>& stacks, int max_H, int next_target) {
	int best_d = candidates[0];
	int avoid_target = next_target + 1; 
	
	for (int c : candidates) {
		bool contains_next = false;
		for (int block : stacks[c]) {
			if (block == avoid_target) {
				contains_next = true;
				break;
			}
		}
		if (!contains_next) {
			best_d = c;
			break; 
		}
	}
	return best_d;
}

// ========================================================================
// DECODER DO PROBLEMA
// ========================================================================

/**************************************************************************
 Method: Decoder 
 Description: Mapeia a solucao de chaves aleatorias para o U-BRP, 
			  retornando o numero de movimentos totais (custo a ser minimizado).
**************************************************************************/
// Vetor unificado de regras heuristicas (facilita testes e adicoes futuras)
std::vector<RuleFunction> heuristic_rules = {
	RuleMinimizarBloqueios,  
	RuleMenosCarregada,	  
	RuleMaisCarregadaViavel, 
	RuleMinMax,			  
	RuleLookAhead			
};
	
int num_rules = heuristic_rules.size();

double Decoder(TSol &s, const TProblemData &data)
{   
	std::vector<std::vector<int>> stacks = data.stacks;
	int n = data.numberOfBlocks; 
	int relocations = 0;

	// Mapeamento de localizacao O(1): bloco -> indice da pilha
	std::vector<int> loc(n + 1, -1);
	for (int i = 0; i < data.numberOfStacks; i++) {
		for (int b : stacks[i]) {
			loc[b] = i;
		}
	}

	int next_target = 1;

	while (next_target <= n) {
		int i = loc[next_target];
		
		if (i < 0) { 
			next_target++; 
			continue; 
		}

		// Desbloqueio: Remove os blocos acima do target atual
		while (!stacks[i].empty() && stacks[i].back() != next_target) {
			int b = stacks[i].back();
			
			double key = (b - 1 < data.n) ? s.rk[b - 1] : 0.5;

			std::vector<int> candidates;
			candidates.reserve(data.numberOfStacks);
			for (int d = 0; d < data.numberOfStacks; d++) {
				if (d != i && (int)stacks[d].size() < data.stackHeight) {
					candidates.push_back(d);
				}
			}

			if (candidates.empty()) {
				return (double)(relocations + 1000000); // Penalidade severa de Deadlock
			}

			// Mapeamento Generico: Transforma a RK [0.0, 1.0) em indice [0, num_rules - 1]
			int rule_idx = (int)(key * num_rules);
			if (rule_idx >= num_rules) rule_idx = num_rules - 1; 

			// Chama a regra sorteada pela metaheuristica
			int best_d = heuristic_rules[rule_idx](b, candidates, stacks, data.stackHeight, next_target);

			// Executa a realocacao
			stacks[i].pop_back();
			stacks[best_d].push_back(b);
			loc[b] = best_d;
			relocations++;

		}

		// Extracao do bloco alvo (agora no topo)
		if (!stacks[i].empty() && stacks[i].back() == next_target) {
			stacks[i].pop_back();
			loc[next_target] = -1; // Marcado como extraido
			
		}
		
		next_target++;
	}

	return (double)relocations;
}

/************************************************************************************
 Method: FreeMemoryProblem
 Description: Free local memory allocate by Problem
*************************************************************************************/
void FreeMemoryProblem(TProblemData &data){
	data.stacks.clear();
}

// ========================================================================
// DESENHO DE SOLUCAO
// ========================================================================

// --- FUNÇÕES DE LOG AUXILIARES ---
void LogInit(const std::vector<std::vector<int>>& stacks, std::ofstream& logEvents) {
    if (!logEvents.is_open()) return;
    logEvents << "INIT\n";
    for (int s = 0; s < (int)stacks.size(); s++) {
        logEvents << "P" << s << ": ";
        for (int b : stacks[s]) logEvents << b << " ";
        logEvents << "\n";
    }
}

void LogRelocation(int block, int from, int to, std::ofstream& logEvents) {
    if (!logEvents.is_open()) return;
    logEvents << "RELOCATE " << block << " " << from << " " << to << "\n";
}

void LogExtraction(int block, std::ofstream& logEvents) {
    if (!logEvents.is_open()) return;
    logEvents << "EXTRACT " << block << "\n";
}

// --- FUNÇÃO QUE RODA 1 ÚNICA VEZ PARA A MELHOR SOLUÇÃO ---
void TraceBestSolution(TProblemData data, TSol s, const char* nameInstance) {

    // 1. Cria o nome do arquivo com base no caminho da instância
    std::filesystem::path p(nameInstance);
    std::string just_the_name = p.filename().string();
    std::string outputLogPath = "../Results/draws/draw-" + just_the_name + listOfMetaheuristics;

    std::ofstream logEvents(outputLogPath);
    if (!logEvents.is_open()) {
        std::cerr << "Erro ao criar arquivo de log de desenho: " << outputLogPath << std::endl;
        return;
    }
	logEvents << "HEIGHT " << data.stackHeight << "\n";
    
    // 2. Clona o estado inicial do pátio
    std::vector<std::vector<int>> stacks = data.stacks;
    std::vector<int> loc(data.numberOfBlocks + 1, -1);
    for (int i = 0; i < data.numberOfStacks; i++) {
        for (int b : stacks[i]) loc[b] = i;
    }

    // Grava a foto inicial
    LogInit(stacks, logEvents);

    int next_target = 1;
    int n = data.numberOfBlocks;

    // 3. Simula a decodificação da solução (CÓPIA DA SUA LÓGICA DO DECODER AQUI)
    while (next_target <= n) {
        int i = loc[next_target];
        if (i < 0) { next_target++; continue; }

        while (!stacks[i].empty() && stacks[i].back() != next_target) {
            int b = stacks[i].back();
            double key = (b - 1 < data.n) ? s.rk[b - 1] : 0.5;

            std::vector<int> candidates;
            for (int d = 0; d < data.numberOfStacks; d++) {
                if (d != i && (int)stacks[d].size() < data.stackHeight) {
                    candidates.push_back(d);
                }
            }

            if (candidates.empty()) break; // Evita loop infinito de deadlock no trace

            // Aqui você aplica a mesma regra do seu Decoder original
            int rule_idx = (int)(key * num_rules);
            if (rule_idx >= num_rules) rule_idx = num_rules - 1; 
            int best_d = heuristic_rules[rule_idx](b, candidates, stacks, data.stackHeight, next_target);

            stacks[i].pop_back();
            stacks[best_d].push_back(b);
            loc[b] = best_d;

            // --- GRAVA O MOVIMENTO ---
            LogRelocation(b, i, best_d, logEvents);
        }

        if (!stacks[i].empty() && stacks[i].back() == next_target) {
            stacks[i].pop_back();
            loc[next_target] = -1; 
            
            // --- GRAVA A EXTRAÇÃO ---
            LogExtraction(next_target, logEvents);
        }
        
        next_target++;
    }

    logEvents.close();
}

#endif
