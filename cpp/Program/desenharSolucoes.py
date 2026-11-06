import sys  
import os
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def parse_events(filename):
	with open(filename, 'r') as f:
		lines = f.read().strip().split('\n')
		
	stacks = []
	events_stream = []
	max_h = 10 # valor default
	
	for line in lines:
		line = line.strip()
		if not line: continue
		
		if line.startswith("HEIGHT"):
			max_h = int(line.split()[1])
		elif line.startswith("P"):
			blocks = line.split(":")[1].strip().split()
			stacks.append([int(b) for b in blocks if b])
		elif line.startswith("RELOCATE") or line.startswith("EXTRACT"):
			events_stream.append(line)

	groups = []
	current_group = {'relocate': None, 'extracts': []}
	
	for event in events_stream:
		if event.startswith("RELOCATE"):
			if current_group['relocate'] or current_group['extracts']:
				groups.append(current_group)
				current_group = {'relocate': None, 'extracts': []}
			
			parts = event.split()
			current_group['relocate'] = {'b': int(parts[1]), 'from': int(parts[2]), 'to': int(parts[3])}
			
		elif event.startswith("EXTRACT"):
			parts = event.split()
			current_group['extracts'].append(int(parts[1]))
			
	if current_group['relocate'] or current_group['extracts']:
		groups.append(current_group)
		
	return stacks, groups, max_h

def plot_single_turn(ax, turn_idx, stacks, relocated_b, extracted_bs, next_relocated_b, max_height):
	num_stacks = len(stacks)
	ax.set_xlim(-0.5, num_stacks)
	ax.set_ylim(0, max_height + 1)
	
	for s_idx, stack in enumerate(stacks):
		for h_idx, block in enumerate(stack):
			
			# --- CORES: Cinza claro para o próximo ---
			if block in extracted_bs:
				facecolor = '#87CEFA' # Azul Claro
			elif block == relocated_b:
				facecolor = '#ff4d4d' # Vermelho Forte
			elif block == next_relocated_b:
				facecolor = '#d3d3d3' # CINZA CLARO
			else:
				facecolor = '#f8f9fa' # Cinza/Branco
				
			rect = patches.Rectangle((s_idx - 0.4, h_idx), 0.8, 0.9, 
									 linewidth=1.5, edgecolor='black', facecolor=facecolor)
			ax.add_patch(rect)
			ax.text(s_idx, h_idx + 0.45, str(block), ha='center', va='center', fontsize=11, fontweight='bold')
			
		ax.plot([s_idx - 0.5, s_idx + 0.5], [0, 0], color='black', linewidth=2)
		ax.text(s_idx, -0.5, f"P{s_idx}", ha='center', va='center', fontsize=9)
	
	# --- TÍTULO NA BASE ---
	actions = []
	if relocated_b is None and not extracted_bs:
		title = f"Turno $t={turn_idx}$ | Config. Inicial"
	else:
		if relocated_b:
			actions.append(f"Realoc {relocated_b}")
		#if extracted_bs:
		#	actions.append(f"Extr {', '.join(map(str, extracted_bs))}")
		title = f"Turno $t={turn_idx}$ | " + ' + '.join(actions)
		
	# O valor y=-0.15 coloca o título abaixo do desenho, mesmo com axis('off')
	#ax.set_title(title, fontsize=10)
	ax.set_title(title, fontsize=9, y=-0.18)
	ax.axis('off')

def simulate_and_plot_grid(initial_stacks, groups, output_filename, max_height=10, cols=3):
	stacks = [list(s) for s in initial_stacks]
	
	total_plots = len(groups) + 1 
	rows = math.ceil(total_plots / cols)
	
	fig, axes = plt.subplots(rows, cols, figsize=(cols * 4, rows * 3.5))
	
	if total_plots == 1:
		axes = [axes]
	else:
		axes = axes.flatten()
		
	# Verifica qual será o primeiro bloco a ser realocado (para o Turno 0)
	next_reloc = None
	if len(groups) > 0 and groups[0]['relocate']:
		next_reloc = groups[0]['relocate']['b']
		
	# --- 1. DESENHA O TURNO 0 ---
	plot_single_turn(axes[0], 0, stacks, None, [], next_reloc, max_height)
	
	turn_idx = 1
	# --- 2. DESENHA OS DEMAIS TURNOS ---
	for i, group in enumerate(groups):
		relocated_b = None
		extracted_bs = group['extracts']
		
		# Aplica a realocação
		if group['relocate']:
			r = group['relocate']
			relocated_b = r['b']
			stacks[r['from']].remove(relocated_b)
			stacks[r['to']].append(relocated_b)
			
		# Verifica quem será realocado no próximo turno (i + 1)
		next_reloc = None
		if i + 1 < len(groups) and groups[i+1]['relocate']:
			next_reloc = groups[i+1]['relocate']['b']
			
		# Desenha no subplot
		plot_single_turn(axes[turn_idx], turn_idx, stacks, relocated_b, extracted_bs, next_reloc, max_height)
		
		# Remove os blocos extraídos para que não apareçam no turno seguinte
		for e in extracted_bs:
			for s in stacks:
				if s and s[-1] == e:
					s.pop()
					break
					
		turn_idx += 1
		
	# --- 3. LIMPEZA DOS SUBPLOTS VAZIOS ---
	for j in range(turn_idx, len(axes)):
		axes[j].axis('off')
		
	plt.tight_layout()
	plt.savefig(output_filename, format='pdf', bbox_inches='tight')
	plt.close()
	
	print(f"Arquivo '{output_filename}' gerado com sucesso (sem deixar arquivos temporários)!")

if __name__ == "__main__":
	# Verifica se os argumentos foram passados no terminal
	if len(sys.argv) < 3:
		print("Uso: python plot_yard.py <arquivo_entrada.txt> <arquivo_saida.pdf>")
		sys.exit(1)
		
	input_txt = sys.argv[1]
	output_pdf = sys.argv[2]

	if os.path.exists(input_txt):
		initial_stacks, event_groups, h = parse_events(input_txt)
		simulate_and_plot_grid(initial_stacks, event_groups, output_filename=output_pdf, max_height=h, cols=3)
	else:
		print(f"Arquivo {input_txt} não encontrado.")
