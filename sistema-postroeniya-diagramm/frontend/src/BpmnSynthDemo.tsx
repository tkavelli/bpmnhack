import React, { useState, useRef, useEffect } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';

const BpmnSynthDemo = () => {
  const [step, setStep] = useState(1);
  const [streamData, setStreamData] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [prompt, setPrompt] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [extractedJson, setExtractedJson] = useState(null);
  const textAreaRef = useRef(null);
  const abortControllerRef = useRef(null);

  useEffect(() => {
    if (textAreaRef.current) {
      textAreaRef.current.scrollTop = textAreaRef.current.scrollHeight;
    }
  }, [streamData]);

  useEffect(() => {
    if (!isLoading && step === 2 && streamData) {
      const afterReasoning = streamData.replace(/^[\s\S]*?\[REASONING_END\]/i, '').trim();
      const jsonMatch = afterReasoning.match(/```json\n([\s\S]*?)```/);
      if (jsonMatch?.[1]) {
        try {
          const parsedJson = JSON.parse(jsonMatch[1]);
          setExtractedJson(parsedJson);
          console.debug("Extracted JSON:", parsedJson);
        } catch (e) {
          console.error("Error parsing JSON:", e);
        }
      }
    }
  }, [streamData, isLoading, step]);

  const handleGenerate = async () => {
    if (!apiKey || !prompt) return;
    
    setStep(2);
    setIsLoading(true);
    setStreamData('');
    
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/formalize_process?descr=${encodeURIComponent(prompt)}&api_key=${encodeURIComponent(apiKey)}`,
        { signal: abortControllerRef.current.signal }
      );

      if (!response.ok || !response.body) throw new Error('Ошибка при запросе потока');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        setStreamData(prev => prev + decoder.decode(value, { stream: true }));
      }

      setIsLoading(false);
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Ошибка при получении потока:', error);
        setIsLoading(false);
      }
    }
  };

  const handleVisualize = async () => {
    if (!extractedJson) return;

    setIsLoading(true);
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/visualize_graph?graph_json=${encodeURIComponent(JSON.stringify(extractedJson))}`
      );
      
      const blob = await response.blob();
      setImageUrl(URL.createObjectURL(blob));
      setStep(3);
    } catch (error) {
      console.error('Ошибка при визуализации:', error);
    }
    setIsLoading(false);
  };

  const handleBack = () => {
    abortControllerRef.current?.abort();
    setIsLoading(false);
    setStep(prev => prev - 1);
  };

  const handleReset = () => {
    abortControllerRef.current?.abort();
    setApiKey('');
    setPrompt('');
    setStreamData('');
    setImageUrl('');
    setExtractedJson(null);
    setIsLoading(false);
    setStep(1);
  };

  return (
    <div style={containerStyle}>
      <div style={contentWrapper}>
        {step === 1 ? (
          <div style={stepContainer}>
            <h2 style={headerStyle}>Шаг 1: Ввод данных</h2>
            <div style={inputsContainer}>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="API ключ"
                style={inputStyle}
              />
              <div style={{...textAreaContainer, flex: 1}}>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Введите описание процесса"
                  style={{...inputStyle, height: '100%', minHeight: '150px'}}
                  rows={5}
                />
              </div>
              <div style={actionButtons}>
                <button
                  onClick={handleGenerate}
                  disabled={!apiKey || !prompt}
                  style={buttonStyle(false, '150px')}
                >
                  Продолжить
                </button>
              </div>
            </div>
          </div>
        ) : step === 2 ? (
          <div style={resultContainer}>
            <h2 style={headerStyle}>Шаг 2: Результат генерации</h2>
            <div style={resultWrapper}>
              <textarea
                ref={textAreaRef}
                value={streamData}
                readOnly
                style={outputStyle}
                placeholder={isLoading ? 'Получение данных...' : 'Результат появится здесь...'}
              />
              {isLoading && <div style={loadingIndicator}>Загрузка...</div>}
            </div>
            <div style={actionButtons}>
              <button
                onClick={handleBack}
                style={buttonStyle(false, '100px', '#6c757d')}
              >
                Назад
              </button>
              <button
                onClick={handleVisualize}
                disabled={isLoading || !extractedJson}
                style={buttonStyle(false, '100px', '#28a745')}
              >
                Далее
              </button>
            </div>
          </div>
        ) : (
          <div style={visualizationContainer}>
            <h2 style={headerStyle}>Шаг 3: Визуализация процесса</h2>
            <div style={imageWrapper}>
              {imageUrl && (
                <TransformWrapper
                  key={imageUrl}
                  initialScale={1}
                  minScale={0.5}
                  maxScale={8}
                  wheel={{ step: 0.08 }}
                  doubleClick={{ disabled: true }}
                >
                  {() => (
                    <TransformComponent
                      wrapperStyle={{
                        width: '100%',
                        height: '100%',
                      }}
                    >
                      <img 
                        src={imageUrl} 
                        alt="Визуализация процесса" 
                        style={imageStyle}
                        onLoad={() => URL.revokeObjectURL(imageUrl)}
                      />
                    </TransformComponent>
                  )}
                </TransformWrapper>
              )}
            </div>
            <div style={actionButtons}>
              <button
                onClick={handleBack}
                style={buttonStyle(false, '100px', '#6c757d')}
              >
                Назад
              </button>
              <button
                onClick={handleReset}
                style={buttonStyle(false, '100px', '#dc3545')}
              >
                Сбросить
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Стили
const containerStyle = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'flex-start',
  minHeight: '100vh',
  padding: '5vh 0'
};

const contentWrapper = {
  width: '70vw',
  height: '90vh',
  display: 'flex',
  flexDirection: 'column',
  gap: '20px'
};

const headerStyle = {
  margin: '0 0 20px 0',
  color: '#333',
  fontSize: '24px',
  fontWeight: '600'
};

const stepContainer = {
  display: 'flex',
  flexDirection: 'column',
  gap: '15px',
  flex: 1
};

const inputsContainer = {
  display: 'flex',
  flexDirection: 'column',
  gap: '15px',
  flex: 1
};

const textAreaContainer = {
  display: 'flex',
  flexDirection: 'column'
};

const inputStyle = {
  padding: '12px',
  borderRadius: '6px',
  border: '1px solid #ddd',
  fontSize: '14px',
  background: '#fff',
  boxSizing: 'border-box',
  width: '100%'
};

const buttonStyle = (isDisabled, width, color = '#007bff') => ({
  padding: '12px 24px',
  backgroundColor: isDisabled ? '#e9ecef' : color,
  color: isDisabled ? '#6c757d' : 'white',
  border: 'none',
  borderRadius: '6px',
  cursor: isDisabled ? 'not-allowed' : 'pointer',
  fontSize: '16px',
  fontWeight: '500',
  transition: 'background-color 0.2s',
  width: width,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  '&:hover:not(:disabled)': {
    backgroundColor: isDisabled ? '#e9ecef' : color === '#007bff' ? '#0056b3' : color
  }
});

const resultContainer = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  gap: '20px'
};

const resultWrapper = {
  flex: 1,
  position: 'relative',
  border: '1px solid #ddd',
  borderRadius: '8px',
  overflow: 'hidden'
};

const outputStyle = {
  padding: '20px',
  border: 'none',
  outline: 'none',
  resize: 'none',
  fontSize: '16px',
  lineHeight: '1.6',
  fontFamily: 'monospace',
  boxSizing: 'border-box',
  backgroundColor: '#f9f9f9',
  width: '100%',
  height: '100%'
};

const loadingIndicator = {
  position: 'absolute',
  bottom: '10px',
  right: '10px',
  color: '#666',
  fontSize: '14px'
};

const actionButtons = {
  display: 'flex',
  gap: '10px',
  justifyContent: 'flex-end'
};

const visualizationContainer = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  gap: '20px'
};

const imageWrapper = {
  flex: 1,
  position: 'relative',
  border: '1px solid #ddd',
  borderRadius: '8px',
  overflow: 'hidden',
  backgroundColor: '#f9f9f9',
  minHeight: '300px'
};

const imageStyle = {
  width: '100%',
  height: '100%',
  objectFit: 'contain',
  cursor: 'grab',
  ':active': {
    cursor: 'grabbing'
  }
};

export default BpmnSynthDemo;