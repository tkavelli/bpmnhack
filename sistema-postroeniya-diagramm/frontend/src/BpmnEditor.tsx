import React, { useEffect, useRef } from 'react';
import BpmnModeler from 'bpmn-js/lib/Modeler';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn.css';

const BpmnEditor = () => {
  const containerRef = useRef(null);
  const modelerRef = useRef(null);

  useEffect(() => {
    const modeler = new BpmnModeler({
      container: containerRef.current,
      keyboard: { bindTo: document }
    });
    modelerRef.current = modeler;

    const initializeDiagram = async () => {
      try {
        await modeler.createDiagram();
        const modeling = modeler.get('modeling');
        const elementFactory = modeler.get('elementFactory');
        const canvas = modeler.get('canvas');
        const elementRegistry = modeler.get('elementRegistry');
        
        const rootElement = canvas.getRootElement();
        
        // Находим существующее стартовое событие
        const startEvents = elementRegistry.filter(element => element.type === 'bpmn:StartEvent');
        const existingStartEvent = startEvents.length > 0 ? startEvents[0] : null;

        // Создаем конечное событие
        const endEvent = elementFactory.createShape({
          type: 'bpmn:EndEvent',
          x: 300,
          y: 100
        });
        modeling.createShape(endEvent, { x: 300, y: 100 }, rootElement);

        // Если есть существующее стартовое событие - соединяем
        if (existingStartEvent) {
          modeling.connect(existingStartEvent, endEvent);
        } else {
          console.warn('Не найдено стартовое событие для соединения');
        }
        
        canvas.zoom('fit-viewport');
      } catch (err) {
        console.error('Ошибка инициализации диаграммы:', err);
      }
    };

    initializeDiagram();

    return () => modelerRef.current?.destroy();
  }, []);

  return (
    <div style={{ 
      position: 'relative',
      width: '100%',
      height: '100vh',
      minWidth: '1850px',
      minHeight: '600px'
    }}>
      <div 
        ref={containerRef}
        style={{ 
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          border: '1px solid #ccc',
          borderRadius: '4px'
        }}
      />
    </div>
  );
};

export default BpmnEditor;