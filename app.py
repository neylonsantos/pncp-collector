#!/usr/bin/env python3
"""
PNCP Collector & Analyzer - Backend Server
Desenvolvido para captura de editais e dados do PNCP (Portal Nacional de Contratações Públicas).
Utiliza exclusivamente a biblioteca padrão do Python 3 (sem necessidade de pip).
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import threading
import uuid
import csv
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Headers que simulam um navegador moderno para evitar bloqueios do WAF Serpro
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://pncp.gov.br/app/editais",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# Cache de resultados em memória para exportação rápida
RESULT_CACHE = {}
CACHE_LOCK = threading.Lock()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def fazer_requisicao_pncp(url, timeout=25, retries=3):
    """Executa requisição GET ao PNCP com tratamento de retry."""
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    ultimo_erro = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", errors="ignore")
            ultimo_erro = f"HTTP {e.code}: {corpo}"
            if e.code in (400, 404):  # Erros que não adianta tentar de novo
                break
            time.sleep(0.5 * (attempt + 1))
        except Exception as e:
            ultimo_erro = str(e)
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(ultimo_erro or "Erro desconhecido na requisição")

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log simplificado
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} - {args[1]}\n")

    def end_headers_cors(self, content_type="application/json; charset=utf-8"):
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers_cors()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # 1. Rota raiz e estáticos
        if path == "/" or path == "/index.html":
            self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            full_path = os.path.join(STATIC_DIR, rel_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                ext = os.path.splitext(full_path)[1].lower()
                mime = "text/plain"
                if ext == ".html": mime = "text/html; charset=utf-8"
                elif ext == ".css": mime = "text/css; charset=utf-8"
                elif ext == ".js": mime = "application/javascript; charset=utf-8"
                elif ext == ".json": mime = "application/json; charset=utf-8"
                elif ext in (".png", ".jpg", ".jpeg", ".svg"): mime = f"image/{ext[1:]}"
                self.serve_file(full_path, mime)
                return
            else:
                self.send_error(404, "Arquivo estático não encontrado")
                return

        # 2. Status e Health Check
        if path == "/api/status":
            self.send_response(200)
            self.end_headers_cors()
            self.wfile.write(json.dumps({
                "status": "online",
                "timestamp": datetime.now().isoformat(),
                "python_version": sys.version
            }).encode("utf-8"))
            return

        # 3. Stream SSE para Coleta e Progresso em Tempo Real
        if path == "/api/stream":
            self.handle_sse_stream(params)
            return

        # 4. Obter Resultados em JSON por ID de Sessão
        if path == "/api/results":
            cache_id = params.get("id", [""])[0]
            with CACHE_LOCK:
                cached = RESULT_CACHE.get(cache_id)
            if not cached:
                self.send_response(404)
                self.end_headers_cors()
                self.wfile.write(json.dumps({"error": "Sessão não encontrada ou expirada"}).encode("utf-8"))
                return
            self.send_response(200)
            self.end_headers_cors()
            self.wfile.write(json.dumps(cached).encode("utf-8"))
            return

        # 5. Exportar JSON Completo
        if path == "/api/export/json":
            cache_id = params.get("id", [""])[0]
            with CACHE_LOCK:
                cached = RESULT_CACHE.get(cache_id)
            if not cached:
                self.send_error(404, "Dados não encontrados")
                return
            
            termo = cached.get("params", {}).get("q", "editais").replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pncp_{termo}_{timestamp}.json"
            
            payload = json.dumps(cached.get("items", []), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
            return

        # 6. Exportar CSV (Formatado para Excel com UTF-8 BOM)
        if path == "/api/export/csv":
            cache_id = params.get("id", [""])[0]
            with CACHE_LOCK:
                cached = RESULT_CACHE.get(cache_id)
            if not cached:
                self.send_error(404, "Dados não encontrados")
                return
            
            items = cached.get("items", [])
            termo = cached.get("params", {}).get("q", "editais").replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pncp_{termo}_{timestamp}.csv"
            
            csv_bytes = self.generate_csv(items)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(csv_bytes)
            return

        # 7. Consultar Itens Detalhados de um Edital
        if path == "/api/edital/itens":
            cnpj = params.get("cnpj", [""])[0]
            ano = params.get("ano", [""])[0]
            seq = params.get("sequencial", [""])[0]
            if not (cnpj and ano and seq):
                self.send_response(400)
                self.end_headers_cors()
                self.wfile.write(json.dumps({"error": "Parâmetros 'cnpj', 'ano' e 'sequencial' são obrigatórios"}).encode("utf-8"))
                return
            url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
            try:
                data = fazer_requisicao_pncp(url)
                self.send_response(200)
                self.end_headers_cors()
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers_cors()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # 8. Consultar Arquivos / PDFs de um Edital
        if path == "/api/edital/arquivos":
            cnpj = params.get("cnpj", [""])[0]
            ano = params.get("ano", [""])[0]
            seq = params.get("sequencial", [""])[0]
            if not (cnpj and ano and seq):
                self.send_response(400)
                self.end_headers_cors()
                self.wfile.write(json.dumps({"error": "Parâmetros 'cnpj', 'ano' e 'sequencial' são obrigatórios"}).encode("utf-8"))
                return
            url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
            try:
                data = fazer_requisicao_pncp(url)
                self.send_response(200)
                self.end_headers_cors()
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers_cors()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_error(404, "Rota não encontrada")

    def serve_file(self, full_path, mime):
        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Erro ao ler arquivo: {e}")

    def generate_csv(self, items):
        """Gera bytes CSV com BOM para garantir que o Microsoft Excel abra em UTF-8 perfeitamente."""
        output = io.StringIO()
        fieldnames = [
            "numero_controle_pncp",
            "titulo",
            "orgao_cnpj",
            "orgao_nome",
            "esfera",
            "poder",
            "uf",
            "municipio",
            "modalidade",
            "tipo_documento",
            "situacao",
            "valor_total_estimado",
            "valor_total_homologado",
            "data_publicacao_pncp",
            "data_inicio_propostas",
            "data_fim_propostas",
            "objeto_resumo",
            "informacao_complementar",
            "link_sistema_origem",
            "possui_itens_detalhados",
            "quantidade_itens"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        
        for item in items:
            itens_detalhes = item.get("_itens_detalhados", [])
            row = {
                "numero_controle_pncp": item.get("numero_controle_pncp", ""),
                "titulo": item.get("title", ""),
                "orgao_cnpj": item.get("orgao_cnpj", ""),
                "orgao_nome": item.get("orgao_nome", ""),
                "esfera": item.get("esfera_nome", ""),
                "poder": item.get("poder_nome", ""),
                "uf": item.get("uf", ""),
                "municipio": item.get("municipio_nome", ""),
                "modalidade": item.get("modalidade_licitacao_nome", ""),
                "tipo_documento": item.get("tipo_nome", ""),
                "situacao": item.get("situacao_nome", ""),
                "valor_total_estimado": str(item.get("valor_total_estimado") or 0.0).replace(".", ","),
                "valor_total_homologado": str(item.get("valor_total_homologado") or 0.0).replace(".", ","),
                "data_publicacao_pncp": item.get("data_publicacao_pncp", ""),
                "data_inicio_propostas": item.get("data_inicio_recebimento_propostas", ""),
                "data_fim_propostas": item.get("data_fim_recebimento_propostas", ""),
                "objeto_resumo": (item.get("description") or "").replace("\n", " ").replace(";", " "),
                "informacao_complementar": (item.get("informacao_complementar") or "").replace("\n", " ").replace(";", " "),
                "link_sistema_origem": item.get("link_sistema_origem", ""),
                "possui_itens_detalhados": "SIM" if itens_detalhes else "NAO",
                "quantidade_itens": len(itens_detalhes)
            }
            writer.writerow(row)
        
        csv_text = output.getvalue()
        # UTF-8 BOM: b'\xef\xbb\xbf'
        return b"\xef\xbb\xbf" + csv_text.encode("utf-8")

    def handle_sse_stream(self, params):
        """Gerencia o streaming SSE de busca com feedback em tempo real de tempo e progresso."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_sse(event_type, data):
            try:
                msg = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()
                return True
            except Exception:
                return False

        q = params.get("q", [""])[0].strip()
        data_inicio = params.get("data_inicio", [""])[0].strip()
        data_fim = params.get("data_fim", [""])[0].strip()
        uf = params.get("uf", [""])[0].strip().upper()
        esfera = params.get("esfera", [""])[0].strip()
        status = params.get("status", [""])[0].strip()
        max_records_str = params.get("max_records", ["0"])[0].strip()
        incluir_itens = params.get("incluir_itens", ["false"])[0].lower() in ("true", "1", "s", "sim")

        try:
            max_records = int(max_records_str)
        except ValueError:
            max_records = 0

        if not q:
            send_sse("error", {"message": "Informe um termo de busca no campo 'q'."})
            return

        start_time = time.time()
        tam_pagina = 500  # Máximo por requisição permitido pelo PNCP
        pagina = 1
        items_coletados = []
        total_estimado = 0
        cache_id = str(uuid.uuid4())

        # 1. Primeira consulta para verificar total e integridade
        query_dict = {
            "q": q,
            "tipos_documento": "edital",
            "pagina": pagina,
            "tam_pagina": min(tam_pagina, max_records) if max_records > 0 else tam_pagina,
            "ordenacao": "-data"
        }
        if data_inicio: query_dict["data_publicacao_inicio"] = data_inicio
        if data_fim: query_dict["data_publicacao_fim"] = data_fim
        if uf: query_dict["ufs"] = uf
        if esfera: query_dict["esferas"] = esfera
        if status: query_dict["status"] = status

        url_inicial = f"https://pncp.gov.br/api/search/?{urllib.parse.urlencode(query_dict)}"
        send_sse("log", {"message": f"Conectando ao PNCP com termo '{q}'...", "level": "info"})

        try:
            primeira_resposta = fazer_requisicao_pncp(url_inicial)
        except Exception as e:
            send_sse("error", {"message": f"Falha na comunicação inicial com o PNCP: {e}"})
            return

        total_estimado = primeira_resposta.get("total", 0)
        primeiros_items = primeira_resposta.get("items", [])
        
        # Define limite efetivo
        total_alvo = total_estimado
        if max_records > 0 and max_records < total_alvo:
            total_alvo = max_records

        send_sse("start", {
            "total_encontrado": total_estimado,
            "total_alvo": total_alvo,
            "termo": q,
            "filtros": {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "uf": uf,
                "esfera": esfera,
                "status": status
            }
        })

        items_coletados.extend(primeiros_items[:total_alvo])
        elapsed = time.time() - start_time
        speed = len(items_coletados) / elapsed if elapsed > 0 else 0
        restante = total_alvo - len(items_coletados)
        eta = restante / speed if speed > 0 else 0

        send_sse("progress", {
            "pagina": pagina,
            "coletados": len(items_coletados),
            "total_alvo": total_alvo,
            "total_encontrado": total_estimado,
            "elapsed_seconds": round(elapsed, 2),
            "eta_seconds": round(eta, 2),
            "speed_items_per_sec": round(speed, 1),
            "percentual": round((len(items_coletados) / total_alvo) * 100, 1) if total_alvo > 0 else 100,
            "batch_size": len(primeiros_items)
        })

        # 2. Loop de paginação
        while len(items_coletados) < total_alvo:
            pagina += 1
            # Respeita o limite do Elasticsearch (pagina * tam_pagina <= 10000)
            if pagina * tam_pagina > 10000:
                send_sse("log", {
                    "message": "Atingida a janela máxima de 10.000 registros do índice do PNCP. Para coletar mais, refine com intervalos de datas menores.",
                    "level": "warn"
                })
                break

            query_dict["pagina"] = pagina
            url_page = f"https://pncp.gov.br/api/search/?{urllib.parse.urlencode(query_dict)}"

            try:
                resp = fazer_requisicao_pncp(url_page)
                batch = resp.get("items", [])
                if not batch:
                    break

                faltam = total_alvo - len(items_coletados)
                items_coletados.extend(batch[:faltam])

                elapsed = time.time() - start_time
                speed = len(items_coletados) / elapsed if elapsed > 0 else 0
                restante = total_alvo - len(items_coletados)
                eta = restante / speed if speed > 0 else 0

                if not send_sse("progress", {
                    "pagina": pagina,
                    "coletados": len(items_coletados),
                    "total_alvo": total_alvo,
                    "total_encontrado": total_estimado,
                    "elapsed_seconds": round(elapsed, 2),
                    "eta_seconds": round(eta, 2),
                    "speed_items_per_sec": round(speed, 1),
                    "percentual": round((len(items_coletados) / total_alvo) * 100, 1) if total_alvo > 0 else 100,
                    "batch_size": len(batch)
                }):
                    # Cliente desconectou
                    return

                time.sleep(0.15)  # Intervalo de gentileza com o servidor do PNCP
            except Exception as e:
                send_sse("log", {"message": f"Erro na página {pagina}: {e}. Tentando continuar...", "level": "warn"})
                time.sleep(0.5)

        # 3. Coleta detalhada de itens individuais (se solicitado)
        if incluir_itens and items_coletados:
            send_sse("log", {
                "message": f"Iniciando captura de itens detalhados para {len(items_coletados)} editais...",
                "level": "info"
            })
            for idx, edital in enumerate(items_coletados):
                cnpj = edital.get("orgao_cnpj")
                ano = edital.get("ano")
                seq = edital.get("numero_sequencial")
                if cnpj and ano and seq:
                    try:
                        url_item = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
                        itens_resp = fazer_requisicao_pncp(url_item, timeout=10, retries=1)
                        if isinstance(itens_resp, list):
                            edital["_itens_detalhados"] = itens_resp
                    except Exception:
                        edital["_itens_detalhados"] = []
                
                # Feedback a cada 10 editais detalhados
                if (idx + 1) % 10 == 0 or idx == len(items_coletados) - 1:
                    elapsed = time.time() - start_time
                    send_sse("item_progress", {
                        "detalhados": idx + 1,
                        "total": len(items_coletados),
                        "elapsed_seconds": round(elapsed, 2)
                    })
                time.sleep(0.05)

        tempo_total = round(time.time() - start_time, 2)

        # 4. Cálculo de estatísticas e métricas para dashboard
        total_valor = 0.0
        esferas_count = {}
        ufs_count = {}
        modalidades_count = {}

        for item in items_coletados:
            val = item.get("valor_total_estimado") or 0.0
            total_valor += float(val) if isinstance(val, (int, float)) else 0.0
            
            esf = item.get("esfera_nome") or "Não Informada"
            esferas_count[esf] = esferas_count.get(esf, 0) + 1
            
            uf_sigla = item.get("uf") or "Outro"
            ufs_count[uf_sigla] = ufs_count.get(uf_sigla, 0) + 1
            
            mod = item.get("modalidade_licitacao_nome") or "Outra"
            modalidades_count[mod] = modalidades_count.get(mod, 0) + 1

        summary = {
            "total_coletado": len(items_coletados),
            "total_disponivel": total_estimado,
            "tempo_total_segundos": tempo_total,
            "velocidade_media": round(len(items_coletados) / tempo_total, 1) if tempo_total > 0 else 0,
            "valor_total_estimado": round(total_valor, 2),
            "esferas": esferas_count,
            "ufs_top": sorted(ufs_count.items(), key=lambda x: x[1], reverse=True)[:10],
            "modalidades": modalidades_count
        }

        # Armazena em cache para download JSON / CSV
        with CACHE_LOCK:
            RESULT_CACHE[cache_id] = {
                "params": query_dict,
                "summary": summary,
                "items": items_coletados,
                "timestamp": datetime.now().isoformat()
            }
            # Limita cache a 10 pesquisas recentes
            if len(RESULT_CACHE) > 10:
                oldest = next(iter(RESULT_CACHE))
                del RESULT_CACHE[oldest]

        send_sse("done", {
            "cache_id": cache_id,
            "summary": summary,
            "sample_items": items_coletados[:50]  # Amostra para renderização inicial rápida
        })

def run_server(port=PORT):
    server = ThreadedHTTPServer(("0.0.0.0", port), RequestHandler)
    print("=" * 65)
    print("  🚀 PNCP Collector & Analyzer - Servidor Ativo!")
    print(f"  🌐 Acesse no seu navegador: http://localhost:{port}")
    print(f"  📂 Pasta do Repositório: {BASE_DIR}")
    print("  Pressione Ctrl+C para encerrar o servidor.")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
        server.server_close()

if __name__ == "__main__":
    run_server()
