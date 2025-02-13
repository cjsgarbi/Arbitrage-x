export class BinanceService {
    constructor() {
        this.baseWsUrl = 'wss://stream.binance.com:9443/ws';
        this.subscriptions = new Set();
        this.symbolsInfo = new Map();
        this.callbacks = new Map();
        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket(this.baseWsUrl);
            
            this.ws.onopen = () => {
                console.log('✅ Conectado à Binance');
                this.resubscribe();
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.ws.onclose = () => {
                console.log('❌ Desconectado da Binance');
                setTimeout(() => this.connect(), 5000);
            };

            this.ws.onerror = (error) => {
                console.error('Erro na conexão WebSocket:', error);
            };
        } catch (error) {
            console.error('Erro ao conectar com Binance:', error);
            setTimeout(() => this.connect(), 5000);
        }
    }

    resubscribe() {
        if (this.subscriptions.size > 0) {
            const subscribeMsg = {
                method: 'SUBSCRIBE',
                params: Array.from(this.subscriptions),
                id: Date.now()
            };
            this.ws.send(JSON.stringify(subscribeMsg));
        }
    }

    subscribeToSymbol(symbol, callback) {
        const streamName = `${symbol.toLowerCase()}@ticker`;
        
        if (!this.callbacks.has(streamName)) {
            this.callbacks.set(streamName, new Set());
        }
        this.callbacks.get(streamName).add(callback);

        if (!this.subscriptions.has(streamName)) {
            this.subscriptions.add(streamName);
            if (this.ws.readyState === WebSocket.OPEN) {
                const subscribeMsg = {
                    method: 'SUBSCRIBE',
                    params: [streamName],
                    id: Date.now()
                };
                this.ws.send(JSON.stringify(subscribeMsg));
            }
        }
    }

    unsubscribeFromSymbol(symbol, callback) {
        const streamName = `${symbol.toLowerCase()}@ticker`;
        
        if (this.callbacks.has(streamName)) {
            this.callbacks.get(streamName).delete(callback);
            
            if (this.callbacks.get(streamName).size === 0) {
                this.callbacks.delete(streamName);
                this.subscriptions.delete(streamName);
                
                if (this.ws.readyState === WebSocket.OPEN) {
                    const unsubscribeMsg = {
                        method: 'UNSUBSCRIBE',
                        params: [streamName],
                        id: Date.now()
                    };
                    this.ws.send(JSON.stringify(unsubscribeMsg));
                }
            }
        }
    }

    handleMessage(data) {
        // Ignora mensagens de resposta de subscrição
        if (data.result === undefined) {
            const streamName = `${data.s.toLowerCase()}@ticker`;
            if (this.callbacks.has(streamName)) {
                const priceData = {
                    symbol: data.s,
                    lastPrice: parseFloat(data.c),
                    priceChange: parseFloat(data.p),
                    priceChangePercent: parseFloat(data.P),
                    volume: parseFloat(data.v),
                    quoteVolume: parseFloat(data.q),
                    high: parseFloat(data.h),
                    low: parseFloat(data.l),
                    timestamp: data.E
                };

                this.callbacks.get(streamName).forEach(callback => {
                    callback(priceData);
                });
            }
        }
    }

    async fetchSymbolsInfo() {
        try {
            const response = await fetch('https://api.binance.com/api/v3/exchangeInfo');
            const data = await response.json();
            
            data.symbols.forEach(symbol => {
                if (symbol.status === 'TRADING') {
                    this.symbolsInfo.set(symbol.symbol, {
                        baseAsset: symbol.baseAsset,
                        quoteAsset: symbol.quoteAsset,
                        filters: symbol.filters,
                        minNotional: symbol.filters.find(f => f.filterType === 'NOTIONAL')?.minNotional || '10',
                        minLotSize: symbol.filters.find(f => f.filterType === 'LOT_SIZE')?.minQty || '1',
                    });
                }
            });
            
            return true;
        } catch (error) {
            console.error('Erro ao buscar informações dos símbolos:', error);
            return false;
        }
    }

    getSymbolInfo(symbol) {
        return this.symbolsInfo.get(symbol);
    }
}