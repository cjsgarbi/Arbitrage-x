import k6

def test_load():
    # Configuração do k6
    k6.config({
        'stages': [
            {'duration': '10s', 'target': 10},
            {'duration': '30s', 'target': 100},
            {'duration': '20s', 'target': 0}
        ]
    })

    # Executa os testes de carga
    k6.run('http://localhost:8000')
