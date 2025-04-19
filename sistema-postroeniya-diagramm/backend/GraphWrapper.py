class GraphWrapper:
    def __init__(self):
        self.nodes = []
        self.edges = []

    def import_from_dict(self, data):
        self.nodes = data.get('nodes', [])
        self.edges = data.get('edges', [])

    def export_to_dict(self):
        return {'nodes': self.nodes, 'edges': self.edges}

    def add_node_before(self, target_node_id, new_node):
        if not any(node['id'] == target_node_id for node in self.nodes):
            raise ValueError(f"Target node {target_node_id} not found")
        
        if any(node['id'] == new_node['id'] for node in self.nodes):
            raise ValueError(f"Node ID {new_node['id']} already exists")
        
        self.nodes.append(new_node)
        
        for edge in self.edges:
            if edge['target'] == target_node_id:
                edge['target'] = new_node['id']
        
        self.edges.append({
            'source': new_node['id'],
            'target': target_node_id
        })

    def check_and_add_end_events(self):
        nodes_to_process = []
        for node in self.nodes:
            node_id = node['id']
            if (node['type'] != 'EndEvent' and 
                not any(edge['source'] == node_id for edge in self.edges)):
                nodes_to_process.append(node)
        
        for node in nodes_to_process:
            base_id = f"endEvent_after_{node['id']}"
            new_end_id = base_id
            counter = 1
            
            while any(n['id'] == new_end_id for n in self.nodes):
                new_end_id = f"{base_id}_{counter}"
                counter += 1
            
            new_end_node = {
                'id': new_end_id,
                'type': 'EndEvent',
                'label': f"Завершение после {node['label']}"
            }
            self.nodes.append(new_end_node)
            
            self.edges.append({
                'source': node['id'],
                'target': new_end_id
            })
    
    def check_and_add_inclusive_gateways(self):
        # Собираем узлы с несколькими входящими связями
        nodes_to_process = []
        for node in self.nodes:
            incoming_edges = sum(1 for edge in self.edges if edge["target"] == node["id"])
            if incoming_edges > 1:
                nodes_to_process.append(node)

        # Добавляем гейтвей для каждого найденного узла
        for node in nodes_to_process:
            base_id = f"gate_before_{node['id']}"
            new_id = base_id
            counter = 1
            
            # Генерация уникального ID
            while any(n["id"] == new_id for n in self.nodes):
                new_id = f"{base_id}_{counter}"
                counter += 1

            # Создаем новый InclusiveGateway
            new_gate = {
                "id": new_id,
                "type": "InclusiveGateway",
                "label": f"Гейт перед {node['label']}"
            }
            
            # Добавляем узел перед текущим
            try:
                self.add_node_before(node["id"], new_gate)
            except ValueError as e:
                print(f"Ошибка при добавлении узла: {e}")