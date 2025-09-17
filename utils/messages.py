from dateutil import parser as dtparser

TEMPLATE = """\
Chamado {key}
{project_name}

Suporte
Nome Contato Cyber: {contato_cyber_nome}
E-mail/Telefone Contato Cyber: {contato_cyber_email_telefone}

TIPO DE ATENDIMENTO: {tipo_atendimento}
Modelo: {modelo}
Serial: {serial}
Hostname: {hostname}
Descrição/Escopo: {descricao}

Por favor, pedir para o técnico tirar foto do ambiente antes de mexer

Endereço: {endereco}
Estado: {estado}
Cidade: {cidade}
Bairro: {bairro}
CEP: {cep}
Complemento: {complemento}

Itens a serem portados pelo técnico
Notebook com Windows a partir da versão 10 e obrigatoriamente o notebook precisa possuir placa de rede ethernet integrada.
Celular com sinal 4G/5G.
Cabo console
Aplicativo PUTTY instalado.
Aplicativo ANYDESK instalado.
01 Filtro de linha (energia).
02 cabos de rede RJ45.

Data/Hora - Agendamento: {data_agendamento} {hora_agendamento}
"""

def build_briefing(issue, fmap, pick_display):
    f = issue.get("fields", {})

    def g(key):
        fid = fmap.get(key)
        if not fid:
            return ""
        return pick_display(f.get(fid))

    data = {
        "key": issue.get("key", ""),
        "project_name": (f.get("project") or {}).get("name", ""),
        "contato_cyber_nome": g("contato_cyber_nome"),
        "contato_cyber_email_telefone": g("contato_cyber_email_telefone"),
        "tipo_atendimento": g("tipo_atendimento"),
        "modelo": g("modelo"),
        "serial": g("serial"),
        "hostname": g("hostname"),
        "descricao": g("descricao") or f.get("summary", ""),
        "endereco": g("endereco"),
        "estado": g("estado"),
        "cidade": g("cidade"),
        "bairro": g("bairro"),
        "cep": g("cep"),
        "complemento": g("complemento"),
        "data_agendamento": g("data_agendamento"),
        "hora_agendamento": g("hora_agendamento"),
        "_created": f.get("created", ""),
    }

    # Se só houver datetime no campo de agendamento, separa data/hora
    if data["data_agendamento"] and not data["hora_agendamento"]:
        try:
            dt = dtparser.parse(data["data_agendamento"])
            data["data_agendamento"] = dt.date().isoformat()
            data["hora_agendamento"] = dt.strftime("%H:%M")
        except Exception:
            pass

    return TEMPLATE.format(**data)
