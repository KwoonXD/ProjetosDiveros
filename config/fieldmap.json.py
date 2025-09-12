{
  "projetos": {
    "FSA": {
      "project_key": "FSA",
      "statuses": {
        "AGENDAMENTO": ["AGENDAMENTO", "Agendamento"],
        "AGENDADO": ["Agendado"],
        "TEC_CAMPO": ["TEC-CAMPO", "Técnico em campo"]
      },
      "fields": {
        "store": "customfield_14954",         // Loja (option/value)
        "pdv": "customfield_14829",
        "asset": "customfield_14825",         // Ativo (option/value)
        "problem": "customfield_12374",
        "address": "customfield_12271",
        "state": "customfield_11948",         // Estado (option/value)
        "zipcode": "customfield_11993",
        "city": "customfield_11994",
        "scheduled_date": "customfield_12036" // Data agendada
      }
    },

    "NOVO": {
      "project_key": "ABC",   // <-- SUBSTITUA pela chave do projeto do novo cliente
      "statuses": {
        "AGENDAMENTO": ["AGENDAMENTO"],       // Ajuste os nomes exatamente como aparecem no Jira
        "AGENDADO": ["Agendado"],
        "TEC_CAMPO": ["TEC-CAMPO"]
      },
      "fields": {
        "store": "customfield_xxxxx",
        "pdv": "customfield_xxxxx",
        "asset": "customfield_xxxxx",
        "problem": "customfield_xxxxx",
        "address": "customfield_xxxxx",
        "state": "customfield_xxxxx",
        "zipcode": "customfield_xxxxx",
        "city": "customfield_xxxxx",
        "scheduled_date": "customfield_xxxxx"
      }
    }
  },

  "padrao": "NOVO"
}
