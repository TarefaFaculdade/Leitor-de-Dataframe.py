# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
import sys
import pandas as pd
import matplotlib.pyplot as plt

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
# 3. Classe responsável por organizar a tabela de acordo com os filtros aplicatos
class CustomRatingFilterProxy(QSortFilterProxyModel):

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
        self.setWindowTitle("Respostas do formulário") #nome da janela
        self.resize(1000, 650) # tamanho total da tela(lagura, alura)
        
        self._dataframe = dataframe #recupera o dataframe armazenado
        self._model = PandasModel(self._dataframe) #recupera o meodelo do dataframe armazenado 
        self._column_names = list(dataframe.columns) #recupera o número total de linhas e colunas


        self._proxy_model = CustomRatingFilterProxy(self)
        self._proxy_model.setSourceModel(self._model)

        self.chart_widget = None

        if len(self._column_names) >  COLUMN_DEFAULT_INDEX:
            self.default_plot_column = self._column_names[COLUMN_DEFAULT_INDEX]
        else:
            self.default_plot_column = self._column_names[0] if self._column_names else "Nenhuma Coluna"
        
        self.initUI() #inicializa o processo de desenhar uma janela
        
    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        #janela principal
        main_layout = QHBoxLayout(central_widget)
        
        outer_sidebar_widget = QWidget()
        outer_sidebar_layout = QVBoxLayout(outer_sidebar_widget)
        outer_sidebar_layout.setContentsMargins(5, 5, 5, 5)
        
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
        checkbox_layout.addWidget(self.chart_label)

        self.chart_widget = MatplotlibCanvas(self, width=4, height=3)
        checkbox_layout.addWidget(self.chart_widget)

        checkbox_layout.addStretch()
        
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

        btn_neg.clicked.connect(lambda: self._proxy_model.set_rating_filter_range(1, 2))
        btn_pos.clicked.connect(lambda: self._proxy_model.set_rating_filter_range(4, 5))
        btn_clear.clicked.connect(self.clear_filters)

        rating_layout.addWidget(btn_neg) #botão negativo
        rating_layout.addWidget(btn_pos) #botão positivo
        rating_layout.addWidget(btn_clear) #botão para limpar seleção
        #=================================================================

        self.scroll_area = QScrollArea() 
        self.scroll_area.setWidgetResizable(True) 
        self.scroll_area.setWidget(checkbox_container) # coloca o container de checkboxes no scrollArea

        # define largura total da tela lateral
        self.scroll_area.setFixedWidth(200)  
        
        checkbox_layout.addWidget(rating_buttons_widget)      

        checkbox_layout.addStretch()

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
        self.display_column_distribution(self.default_plot_column)
    
    # filtra a tabela pelo período de tempo desejado
    def search_timestamp(self, search_txt: str):
        self._proxy_model.set_rating_filter_range(0, 0)

        regex = QRegularExpression(search_txt, QRegularExpression.PatternOption.CaseInsensitiveOption)

        self._proxy_model.setFilterRegularExpression(regex)

    # cria um gráfico baseado na distribuição de respostas
    def display_column_distribution(self, column_name):
        
        if self._dataframe.empty or column_name not in self._dataframe.columns:
             self.chart_label.setText("Coluna Inválida")
             self.graphic_distribution(self.chart_widget.axes, column_name, error_mode=True)
             return

        try:
            # armazena a quantidade e nome das colunas
            data_dist = (self._dataframe[column_name]
                         .value_counts(normalize=True) * 100)
            
            # essa merda tem que estar aqui por algum motivo que eu desconheço 
            html_content = "<b></b><hr style='margin: 2px 0;'>"
            
            # limita a 10 entradas para não esticar demais a barra lateral
            for value, percentage in data_dist.head(10).items():
                
                # cria a string da linha: "Resposta (25.00%)"
                html_content += f"<p style='margin: 0;'>{str(value)}: <b>{percentage:.2f}%</b></p>"

            self.chart_label.setText(f"Distribuição de Respostas: <b>{column_name}</b>")
            self.graphic_distribution(self.chart_widget.axes, column_name)

        except Exception as e:
            self.chart_label.setText(f"Erro ao calcular distribuição: {e}")

    # atualiza esse gráfico todo frame
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

    def update_column_distribution(self, col_index: int, state: int):
        
        should_hide = (state == 0)
        self.view.setColumnHidden(col_index, should_hide)
        
        if state != 0: # Se a checkbox foi marcada (Visível)
            if GRAPHIC_COLUMN_START <= col_index <= GRAPHIC_COLUMN_END:
                column_name = self._column_names[col_index]
                self.display_column_distribution(column_name)
            else:
                error_msg = f"Coluna inválida para análise."
                self.graphic_distribution(self.chart_widget.axes, "N/A", error_mode=True, error_message=error_msg)
            
    def toggle_percentage_visibility(self):
        
        is_visible = self.chart_label.isVisible()
        
        self.chart_label.setVisible(not is_visible)
        self.chart_widget.setVisible(not is_visible)
        self.chart_label.setVisible(not is_visible)
        
        if is_visible:
            self.toggle_dist_btn.setText("Mostrar Porcentagem (%)")
        else:
            self.toggle_dist_btn.setText("Ocultar Porcentagem (%)")


    def filter_ratings(self, column_name: str, range_key: str):
        """Aplica o filtro numérico na coluna de rating."""
        
        # 1. Encontra o índice da coluna de rating
        try:
            col_index = self._column_names.index(column_name)
        except ValueError:
            print(f"Erro: Coluna '{column_name}' não encontrada no DataFrame.")
            return

        # 2. Define a coluna a ser filtrada e o padrão Regex
        self._proxy_model.setFilterKeyColumn(col_index)
        self.search_input.setText("") # Limpa a caixa de pesquisa geral para evitar conflito

        if range_key == 'NEG':
            # Valores 1, 2 ou 3 (Regex: '^1$|^2$|^3$')
            pattern = "^[1-3]$"
        elif range_key == 'POS':
            # Valores 3, 4 ou 5 (Regex: '^3$|^4$|^5$')
            pattern = "^[3-5]$"
        else:
            # Caso inesperado, limpa o filtro
            pattern = ""
            self._proxy_model.setFilterKeyColumn(-1)

        # 3. Aplica o filtro
        regex = QRegularExpression(pattern)
        self._proxy_model.setFilterRegularExpression(regex)

    # Remove todos os filtros e reseta a busca geral.
    def clear_filters(self):
        self._proxy_model.set_rating_filter_range(0, 0)

        self._proxy_model.setFilterRegularExpression("")
        self._proxy_model.setFilterKeyColumn(-1) # Volta a filtrar em todas as colunas
        self.search_input.setText("")
        

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
