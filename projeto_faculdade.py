import sys
import pandas as pd
import matplotlib.pyplot as plt

from google import genai
from google.genai.errors import APIError

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QApplication, QHeaderView, QLineEdit, QMainWindow, QWidget, QTableView, 
    QVBoxLayout, QHBoxLayout, QCheckBox, QScrollArea, QSizePolicy, QHeaderView, QLineEdit, QLabel,
    QPushButton
)
from PyQt6.QtCore import (
  QAbstractTableModel, 
  Qt, 
  QModelIndex,
  QRegularExpression,
  QSortFilterProxyModel
  )

COLUMN_DEFAULT_INDEX = 1

GEMINI_API_KEY = "PEÇA PRA MIM NO PRIVADO"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_MODEL = "gemini-2.5-flash"

# as colunas que podem ser selecionadas para avaliação de positivo e negativo
RATING_COLUMN_START = 2 # inicio
RATING_COLUMN_END = 5 # fim

# as colunas que podem ser selecionadas no gráfico
GRAPHIC_COLUMN_START = 2 # inicio
GRAPHIC_COLUMN_END = 9 # fim

# ===============================================================
# 1. Armaze os valores no dataframe da planilha
class PandasModel(QAbstractTableModel):
    """A model to interface a Qt view with pandas dataframe """

    #inicializador do dataframe
    def __init__(self, dataframe: pd.DataFrame, parent=None):
        QAbstractTableModel.__init__(self, parent) #classe base para criação de modelos em tabela
        self._dataframe = dataframe #armazena o dataframe(informações da planilha como número de linhas e colunas)

    #faz a contagem do número de linhas do dataframe
    def rowCount(self, parent=QModelIndex()) -> int:
        if parent == QModelIndex():
            return len(self._dataframe) #retorna a quantidade de linhas
        return 0

    #faz a contagem do número de colunas
    def columnCount(self, parent=QModelIndex()) -> int:
        if parent == QModelIndex():
            return len(self._dataframe.columns) #retorna a quantidade de colunas
        return 0

    def data(self, index: QModelIndex, role=Qt.ItemDataRole):
        if not index.isValid(): #checa se o dataframe é válido
            return None #nada é retornado

        if role == Qt.ItemDataRole.DisplayRole: #caso alguma coisa precise ser escrita na tabela
            return str(self._dataframe.iloc[index.row(), index.column()]) #define o que deve ser escrito em cada célula da tabela

        return None

    #retona os textos dos cabeçalhos das tabelas
    def headerData(
            self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole
            ):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal: #caso a orientação seja horizontal
                return str(self._dataframe.columns[section]) #retorna o nome das colunas da tabela

            if orientation == Qt.Orientation.Vertical: #caso a orientação seja vertical
                return str(self._dataframe.index[section]) #retorna o nome das linhas da tabela

        return None
# ===============================================================

# ===============================================================
# 2. Adiciona elementos da biblioteca MatPlotLib ao código e os inicia
class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        fig.tight_layout(pad=3.0) 
        super().__init__(fig)
        self.setParent(parent)
# ================================================================

# ================================================================
# 3. Classe responsável por organizar a tabela de acordo com os filtros aplicados
class RatingFilterProxy(QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        # valores de filtro (0, 0) significa filtro desativado
        self.min_val = 0
        self.max_val = 0
        self.start_col = RATING_COLUMN_START
        self.end_col = RATING_COLUMN_END

    def set_rating_filter_range(self, min_val: int, max_val: int):
        self.min_val = min_val
        self.max_val = max_val
        self.invalidateFilter() 

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self.min_val == 0 and self.max_val == 0:
            return True

        model = self.sourceModel()
        
        for col in range(self.start_col, self.end_col + 1):
            index = model.index(source_row, col, source_parent)
            data = model.data(index, Qt.ItemDataRole.DisplayRole)
            
            try:
                # Tenta converter o dado para float/int
                value = float(str(data))
                
                if self.min_val <= value <= self.max_val:
                    return True 
                    
            except (ValueError, TypeError):
                continue

        return False
# =============================================================

# =============================================================
# 4. Classe responsável por controlar como a janela será exibida
class DataFrameViewer(QMainWindow):
    def __init__(self, dataframe: pd.DataFrame):
        super().__init__()

        try:
            self.ai_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            print(f"Erro ao inicializar o cliente Gemini: {e}")
            self.ai_client = None

        self.setWindowTitle("Respostas do formulário") #nome da janela
        self.resize(1000, 650) # tamanho total da tela(lagura, alura)
        
        self._dataframe = dataframe #recupera o dataframe armazenado
        self._model = PandasModel(self._dataframe) #recupera o meodelo do dataframe armazenado 
        self._column_names = list(dataframe.columns) #recupera o número total de linhas e colunas

        self._proxy_model = RatingFilterProxy(self)
        self._proxy_model.setSourceModel(self._model)

        self.chart_widget = None
 
        if len(self._column_names) >  COLUMN_DEFAULT_INDEX:
            self.default_plot_column = self._column_names[COLUMN_DEFAULT_INDEX]
        else:
            self.default_plot_column = self._column_names[0] if self._column_names else "Nenhuma Coluna"
        
        self.initUI() #inicializa o processo de desenhar uma janela

    def get_column_concentration(self, col_index: int) -> str:
        
        column_name = self._column_names[col_index]
        
        series = self._dataframe[column_name].astype(str)
        
        positive_count = series.str.contains('^[45]$').sum()
        negative_count = series.str.contains('^[12]$').sum()

        if positive_count > negative_count:
            return 'POS'
        elif negative_count > positive_count:
            return 'NEG'
        else:
            return 'NEUTRAL'

    def show_all_columns(self):
        for i in range(len(self._column_names)):
            self.view.setColumnHidden(i, False)
            if self._column_names[i] in self.checkboxes:
                self.checkboxes[self._column_names[i]].setChecked(True)

    def filter_columns_concentration(self, target_type: str):
        
        self.show_all_columns() # garante que todas as colunas de avaliação estão visíveis
        self.clear() # limpa filtros anteriores (incluindo a pesquisa de data)

        if target_type == 'POS':
            self._proxy_model.set_rating_filter_range(4, 5)
        elif target_type == 'NEG':
            self._proxy_model.set_rating_filter_range(1, 2)
        elif target_type == 'ALL':
            self._proxy_model.set_rating_filter_range(0, 0)   


    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        #janela principal
        main_layout = QHBoxLayout(central_widget)
        
        # layout secundário específico para checkboxes, gráficos, entre outros itens
        checkbox_container = QWidget()
        checkbox_layout = QVBoxLayout(checkbox_container)# organiza os checkboxes verticalmente
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop) # alinha o conteúdo ao topo

        self.search_input = QLineEdit() # adiciona a aba de pesquisa
        self.search_input.setPlaceholderText("procure por uma data") # adiciona o texto placeholder caso a aba esteja vazia
        self.search_input.textChanged.connect(self.search_timestamp) # procura um valor semelhante na coluna "timestamp"

        checkbox_layout.addWidget(self.search_input)
        
        self.checkboxes = {} #retorna um valor nulo as checkboxes da classe

        scrollable_content_widget = QWidget()
        scrollable_layout = QVBoxLayout(scrollable_content_widget)
        scrollable_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

       
        #===========================================================================================
        # loop que cria uma conexão entre as checkboxes e as colunas da tabela
        for i, col_name in enumerate(self._column_names):
            checkbox = QCheckBox(col_name) # dá o nome de uma coluna a checkbox
            checkbox.setChecked(True) # a checkbox recebe o valor de true, sendo assim, checkbox é considerada marcada
            
            # conexão (slot/signal)
            checkbox.stateChanged.connect(lambda state, col=i: self.update_column_distribution(col, state))
            
            checkbox_layout.addWidget(checkbox) # retorna o valor das checkboxes a tela lateral
            self.checkboxes[col_name] = checkbox

        #===========================================================================================
        
        #===========================================================================================
        # responsável por mostrar as estátisticas em forma de porcentagem
        self.chart_label = QLabel(f"Distribuição de Respostas: {self.default_plot_column}")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        checkbox_layout.addWidget(self.chart_label)

        self.chart_widget = MatplotlibCanvas(self, width=4, height=3)
        checkbox_layout.addWidget(self.chart_widget)

        #=================================================================

        #=================================================================
        # adiciona a função e funcionamento dos botões de avaliação
        checkbox_layout.addWidget(self.chart_label)

        rating_buttons_widget = QWidget()
        rating_layout = QVBoxLayout(rating_buttons_widget)
        rating_layout.setContentsMargins(0, 0, 0, 0)

        btn_neg = QPushButton("Avaliações Negativas") # botão para as avaliações negativas
        btn_pos = QPushButton("Avaliações Positivas") # botão para as avaliações positivas
        btn_clear = QPushButton("Limpar Filtros") # limpa a seleção

        btn_neg.clicked.connect(lambda: self.filter_columns_concentration('NEG'))
        btn_pos.clicked.connect(lambda: self.filter_columns_concentration('POS'))
        btn_clear.clicked.connect(self.clear)

        rating_layout.addWidget(btn_neg) #botão negativo
        rating_layout.addWidget(btn_pos) #botão positivo
        rating_layout.addWidget(btn_clear) #botão para limpar seleção
        #=================================================================

        #=================================================================
        # sessão responsável pela adição dos botões para fazer request da IA
        self.ai_resolution_btn = QPushButton("Gerar Resolução de IA (Linha Selecionada)")
        self.ai_resolution_btn.clicked.connect(self.run_ai_resolution)

        checkbox_layout.addWidget(QLabel("Análise de IA:"))
        checkbox_layout.addWidget(self.ai_resolution_btn)
        #=================================================================

        self.scroll_area = QScrollArea() 
        self.scroll_area.setWidgetResizable(True) 
        self.scroll_area.setWidget(checkbox_container) # coloca o container de checkboxes no scrollArea

        # define largura total da tela lateral
        self.scroll_area.setFixedWidth(200)  
        
        checkbox_layout.addWidget(rating_buttons_widget)      

        # criação do botão de visibilidade para a tabela de barra
        self.toggle_dist_btn = QPushButton("Ocultar Distribuição (%)")
        self.toggle_dist_btn.clicked.connect(self.toggle_percentage_visibility)

        checkbox_layout.addWidget(self.toggle_dist_btn)

        # evita que o texto ultrapasse o tamanho máximo da tela lateral
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        
        # adição da barra lateral a janela principal (Horizontal)
        main_layout.addWidget(self.scroll_area) 
        
        self.view = QTableView() # cria uma tela em formato de tabela 
        self.view.setModel(self._proxy_model) # passa o modelo do dataframe para a tabela me branco criada na linha acima
        
        self.view.setWordWrap(True) # se True o texto quebra linha e se False o texto é cortado
        self.view.resizeRowsToContents() # recalcula o tamanho das linhas

        # permite que o dataframe seja redimensionada verticalmente/horizontalmente com o mouse
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.view.setAlternatingRowColors(True) # altera a cor da coluna selecionada
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows) # permite que fileiras sejam selecionadas
        

        # adiciona a tabela ao layout principal
        main_layout.addWidget(self.view) 
        # adiciona o gráfico de barras a tela
        self.show_column_distribution(self.default_plot_column)
    
    # filtra a tabela pelo período de tempo desejado
    def search_timestamp(self, search_txt: str):
        self.show_all_columns()

        self._proxy_model.set_rating_filter_range(0, 0)
        self._proxy_model.setFilterKeyColumn(-1)

        regex = QRegularExpression(search_txt, QRegularExpression.PatternOption.CaseInsensitiveOption)

        self._proxy_model.setFilterRegularExpression(regex)

    # cria um gráfico baseado na distribuição de respostas
    def show_column_distribution(self, column_name):
        
        if self._dataframe.empty or column_name not in self._dataframe.columns:
             self.chart_label.setText("Coluna Inválida")
             self.graphic_distribution(self.chart_widget.axes, column_name, error_mode=True)
             return

        try:
            # armazena a quantidade e nome das colunas
            data_dist = (self._dataframe[column_name]
                         .value_counts(normalize=True) * 100)
            
            self.chart_label.setText(f"Distribuição de Respostas: <b>{column_name}</b>")
            self.graphic_distribution(self.chart_widget.axes, column_name)

        except Exception as e:
            self.chart_label.setText(f"Erro ao calcular distribuição: {e}")

    # desenha o gráfico em barras na tela
    def graphic_distribution(self, ax, column_name, error_mode=False, error_message="Erro ao gerar gráfico."):
        ax.clear()
        
        if error_mode:
            ax.text(0.5, 0.5, f"Erro: {error_message}", ha='center', va='center', wrap=True, fontsize=10)
            self.chart_widget.draw()
            return
            
        try:
            data_dist = (self._dataframe[column_name].value_counts(normalize=True) * 100)
            
            categories = [str(c) for c in data_dist.head(10).index]
            percentages = data_dist.head(10).values
            
            ax.barh(categories, percentages, color='skyblue')
            
            ax.set_title(f"Distribuição de '{column_name}'", fontsize=10)
            ax.set_xlabel("Percentual (%)", fontsize=8)
            ax.tick_params(axis='y', labelsize=8)
            ax.tick_params(axis='x', labelsize=8)
            ax.invert_yaxis()
            
            for spine in ['right', 'top']:
                ax.spines[spine].set_visible(False)
                
        except Exception as e:
            # Captura erros de plotagem (ex: dados ruins)
            ax.text(0.5, 0.5, f"Erro de Plotagem: {e}", ha='center', va='center', wrap=True, fontsize=10)


        self.chart_widget.draw()

    # atualiza esse gráfico todo frame
    def update_column_distribution(self, col_index: int, state: int):
        
        should_hide = (state == 0)
        self.view.setColumnHidden(col_index, should_hide)
        
        if state != 0: # Se a checkbox foi marcada (Visível)
            if GRAPHIC_COLUMN_START <= col_index <= GRAPHIC_COLUMN_END:
                column_name = self._column_names[col_index]
                self.show_column_distribution(column_name)
            else:
                error_msg = f"Coluna inválida para análise."
                self.graphic_distribution(self.chart_widget.axes, "N/A", error_mode=True, error_message=error_msg)
            
    def toggle_percentage_visibility(self):
        
        is_visible = self.chart_label.isVisible()
        
        self.chart_label.setVisible(not is_visible)
        self.chart_widget.setVisible(not is_visible)
        
        if is_visible:
            self.toggle_dist_btn.setText("Mostrar Porcentagem (%)")
        else:
            self.toggle_dist_btn.setText("Ocultar Porcentagem (%)")

    def clear_filters(self):
        self.show_all_columns()
        self.clear()

    # remove todos os filtros e reseta a busca geral.
    def clear(self):
        self._proxy_model.setFilterRegularExpression("")

        self._proxy_model.setFilterKeyColumn(-1)
        self._proxy_model.set_rating_filter_range(0, 0)
        self.search_input.setText("")

    def prepare_ai_resolution(self, row_data: pd.Series) -> str:
      
        feedback_text = ""
        for col_name, value in row_data.items():
         try:
           col_index = self._column_names.index(col_name)
         except ValueError:
                continue

         if col_index < 2: 
                continue
                
         str_value = str(value) if pd.notna(value) else "" 
            
         if str_value: 
                feedback_text += f"- {col_name} (Col. {col_index}): {str_value}\n"

        prompt = (
                "Você é responsável por administrar os cursos de uma universidade e deve analisar" 
                "as reclamações feitas na tabela e vir com no máximo 3 soluções para o problema"
                "se baseando nas reclamações feitas. Responda em Português do Brasil."
                "cada coluna é reclamação diferente"
                "primeira coluna: Qualidade das aulas(vai de 1 a 5 sendo cinco a maior nota)"
                "segunda coluna: Didática dos professores(1 a 5)"
                "terceira coluna: Comunicação da coordenação(1 a 5)"
                "quarta coluna: Infraestrutura da universidade(banheiros, laboratórios e salas)(1 a 5)"
                "quinta coluna: Avaliação da carga de conteúdos"
                "sexta coluna: Avaliação do conteúdo prático"
                "sétima coluna: Se a pessoa recomendaria a universidade para um conhecido"
                "última coluna: feedback construtivo\n\n"
            f"Dados do Cliente:\n{feedback_text}"
        )
        try:
            response = self.ai_client.models.generate_content(
                model=GEMINI_MODEL, 
                contents=prompt, 
                config= {
                   "response_mime_type": "application/json",
                   "temperature": 0.5,
              }
            )

            return response.text

        except APIError as e:
            status_code = response.status_code if 'response' in locals() else 'N/A'
            return f"Erro de Conexão/API ({status_code}): {e}"
        except Exception as e:
            return f"Erro Inesperado: {e}"

    def run_ai_resolution(self):
        
        selection_model = self.view.selectionModel()
        indexes = selection_model.selectedRows()
        
        if not indexes:
            self.ai_resolution_output.setText("Erro: Nenhuma linha selecionada.")
            return

        proxy_index = indexes[0]
        source_index = self._proxy_model.mapToSource(proxy_index)    
        row = source_index.row()
        
        try:
            selected_row_data = self._dataframe.iloc[row]
            
            if not isinstance(selected_row_data, pd.Series):
                 raise TypeError("Dados extraídos não são uma Series do pandas.")
            
        except IndexError:
            print("Erro: Índice da linha fora dos limites do DataFrame.")
            return
        except Exception as e:
            print(f"Erro ao extrair linha: {e}")
            return
        
        resolution = self.prepare_ai_resolution(selected_row_data)
        print("\n--- RESOLUÇÃO ---")
        print(resolution)
        print("-----------------------\n")
    
# =============================================================
# 4. BLOCO DE EXECUÇÃO

if __name__ == "__main__":
    
    # links do Google Sheets 
    ID = '1qyLigMRwem_Z6Wh6NDkSLFZo5uOngDnJ-XPMswXED8E' 
    GID = '434036813'
    CSV_URL = f'https://docs.google.com/spreadsheets/d/{ID}/gviz/tq?tqx=out:csv&gid={GID}' # os lindos são sempres os mesmos, o diferencial apenas é o ID e GID

    app = QApplication(sys.argv) # inicia o PyQt

    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        print(f"Erro ao carregar dados do Google Sheets: {e}")
        # cria um DataFrame de placeholder em caso de falha de conexão
        df = pd.DataFrame({'Erro': ['Falha ao carregar dados'], 'Detalhe': [str(e)]})
        
    viewer = DataFrameViewer(df) # inicia a janela principal
    viewer.show() # desenha todos os elementos incluindo a janela principal 
    
    sys.exit(app.exec()) # encerra a janela
# =============================================================
