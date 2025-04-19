from graphviz import Digraph
from GraphWrapper import GraphWrapper

def load_bpmn_data(json_data):
    """Загрузка и валидация структуры BPMN из JSON"""
    required_node_fields = ['id', 'type', 'label']
    required_edge_fields = ['source', 'target']
    
    for node in json_data['nodes']:
        if not all(field in node for field in required_node_fields):
            raise ValueError("Invalid node format")

    for edge in json_data['edges']:
        if not all(field in edge for field in required_edge_fields):
            raise ValueError("Invalid edge format")
    
    return json_data

def create_bpmn_graph(data, filename='bpmn_graph'):
    """Создание Graphviz графа из BPMN-описания"""

    # Алгоритмическая доработка графа
    graph = GraphWrapper()
    graph.import_from_dict(data)
    graph.check_and_add_end_events() # Исправление тупиковых узлов
    graph.check_and_add_inclusive_gateways() # Добавляем иклюзивные гейты
    fixed_data = graph.export_to_dict()

    # Инициализация графа
    dot = Digraph(filename, format='png')
    dot.attr(rankdir='LR', splines='ortho')  # Горизонтальная ориентация
    
    # Конфигурация стилей
    node_styles = {
        'StartEvent': {'shape': 'ellipse', 'color': '#4CAF50', 'fillcolor': '#C8E6C9', 'style': 'filled'},
        'EndEvent': {'shape': 'ellipse', 'color': '#F44336', 'fillcolor': '#FFCDD2', 'style': 'filled'},
        'IntermediateCatchEvent': {'shape': 'ellipse', 'color': '#2196F3', 'fillcolor': '#BBDEFB', 'style': 'filled'},
        'IntermediateThrowEvent': {'shape': 'ellipse', 'color': '#9C27B0', 'fillcolor': '#E1BEE7', 'style': 'filled'},
        'BoundaryEvent': {'shape': 'ellipse', 'color': '#FF5722', 'fillcolor': '#FFCCBC', 'style': 'filled,dashed'},
        'UserTask': {'shape': 'rect', 'color': '#2196F3', 'fillcolor': '#BBDEFB', 'style': 'filled,rounded'},
        'ServiceTask': {'shape': 'rect', 'color': '#2196F3', 'fillcolor': '#BBDEFB', 'style': 'filled'},
        'SendTask': {'shape': 'rect', 'color': '#3F51B5', 'fillcolor': '#C5CAE9', 'style': 'filled'},
        'ReceiveTask': {'shape': 'rect', 'color': '#2196F3', 'fillcolor': '#BBDEFB', 'style': 'filled'},
        'ManualTask': {'shape': 'rect', 'color': '#FFC107', 'fillcolor': '#FFECB3', 'style': 'filled,rounded'},
        'BusinessRuleTask': {'shape': 'rect', 'color': '#673AB7', 'fillcolor': '#D1C4E9', 'style': 'filled'},
        'ScriptTask': {'shape': 'rect', 'color': '#607D8B', 'fillcolor': '#CFD8DC', 'style': 'filled'},
        'ExclusiveGateway': {'shape': 'diamond', 'color': '#9C27B0', 'fillcolor': '#E1BEE7', 'style': 'filled'},
        'ParallelGateway': {'shape': 'diamond', 'color': '#FF9800', 'fillcolor': '#FFE0B2', 'style': 'filled'},
        'InclusiveGateway': {'shape': 'diamond', 'color': '#8BC34A', 'fillcolor': '#DCEDC8', 'style': 'filled'},
        'EventBasedGateway': {'shape': 'diamond', 'color': '#7B1FA2', 'fillcolor': '#CE93D8', 'style': 'filled,dashed'},
        'SubProcess': {'shape': 'rect', 'color': '#795548', 'fillcolor': '#D7CCC8', 'style': 'filled,rounded'},
        'CallActivity': {'shape': 'rect', 'color': '#795548', 'fillcolor': '#D7CCC8', 'style': 'filled,rounded,dashed'},
        'TextAnnotation': {'shape': 'note', 'color': '#000000', 'fillcolor': '#FFFFFF', 'style': 'filled'}
        }   
    
    # Добавление узлов
    for node in fixed_data['nodes']:
        node_type = node['type']
        style = node_styles.get(node_type, {})
        
        dot.node(
            name=node['id'],
            label=f"{node['label']}\n({node['id']})",
            **style
        )
    
    # Добавление связей
    for edge in fixed_data['edges']:
        label = edge.get('label', '')
        if edge.get('condition'):
            label += f"\n[{edge['condition']}]" if label else edge['condition']
        
        dot.edge(
            edge['source'],
            edge['target'],
            label=label,
            fontsize='10',
            fontcolor='#616161'
        )
    
    return dot