"""Genera docs/02-design/contracts/asyncapi.yaml desde los modelos pydantic del dominio."""
import sys

import yaml

from src.domain.models import Adjunto, ResultadoClasificado

REF = "#/components/schemas/{model}"

resultado = ResultadoClasificado.model_json_schema(ref_template=REF)
schemas = resultado.pop("$defs", {})
adjunto = Adjunto.model_json_schema(ref_template=REF)
schemas.update(adjunto.pop("$defs", {}))
schemas["Adjunto"] = adjunto
resultado["properties"]["payload"]["description"] = (
    "Datos para el servicio aguas abajo. Hoy: `texto` (string saneado) y `adjuntos` "
    "(lista de Adjunto). Vacío cuando la entrada fue bloqueada."
)
schemas["ResultadoClasificado"] = resultado

schemas["WebhookMeta"] = {
    "type": "object",
    "description": (
        "Webhook estándar de Meta. El servicio solo lee los campos listados y procesa "
        "el primer mensaje válido; el resto del documento se ignora."
    ),
    "required": ["object", "entry"],
    "additionalProperties": True,
    "properties": {
        "object": {
            "type": "string",
            "enum": ["page", "instagram", "whatsapp_business_account"],
            "description": "Identifica la plataforma: page es Messenger.",
        },
        "entry": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "messaging": {
                        "type": "array",
                        "description": "Messenger e Instagram: eventos con sender.id, timestamp en ms y message (mid, text, attachments).",
                        "items": {"type": "object", "additionalProperties": True},
                    },
                    "changes": {
                        "type": "array",
                        "description": "WhatsApp Cloud API: value.messages[] con id, from, timestamp en s, type y el cuerpo según el tipo.",
                        "items": {"type": "object", "additionalProperties": True},
                    },
                },
            },
        },
    },
}

schemas["SobreCustomWhatsApp"] = {
    "type": "object",
    "description": (
        "Sobre que emite el receptor aguas arriba para WhatsApp. Pese al nombre del campo, "
        "el contenido llega en claro. El servicio solo lee jwe_body.type y "
        "jwe_body.message.messages[0]."
    ),
    "required": ["jwe_body"],
    "additionalProperties": True,
    "properties": {
        "eventId": {"type": "string", "description": "Identificador del evento aguas arriba. Hoy no se propaga."},
        "jwe_body": {
            "type": "object",
            "required": ["type", "message"],
            "additionalProperties": True,
            "properties": {
                "type": {"type": "string", "enum": ["whatsapp_business_account"]},
                "botId": {"type": "string", "description": "Bot destinatario. Hoy no se propaga."},
                "contact": {"type": "object", "additionalProperties": True, "description": "Nombre y waId del contacto. Dato personal; no se usa."},
                "message": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "messages": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                    },
                },
            },
        },
    },
}

AMQP = "0.3.0"

doc = {
    "asyncapi": "3.0.0",
    "info": {
        "title": "ms-python-metamsghandler",
        "version": "0.2.0",
        "description": (
            "Contrato de mensajería del worker de clasificación de mensajes de Meta. "
            "Consume webhooks de una cola de RabbitMQ y publica un ResultadoClasificado en otra. "
            "Los esquemas de salida se generan desde los modelos pydantic de src/domain/models."
        ),
    },
    "defaultContentType": "application/json",
    "servers": {
        "rabbitmq": {
            "host": "{qms_server}:{qms_port}",
            "protocol": "amqp",
            "protocolVersion": "0.9.1",
            "description": "Broker compartido con el receptor de webhooks y el servicio de respuesta. Hoy sin TLS (amenaza T5).",
            "variables": {
                "qms_server": {"description": "Host del broker (variable qms_server)."},
                "qms_port": {"description": "Puerto del broker (variable qms_port).", "default": "5672"},
            },
            "security": [{"$ref": "#/components/securitySchemes/usuarioBroker"}],
        }
    },
    "channels": {
        "entrada": {
            "address": "{queue_name}",
            "description": "Cola durable con los webhooks crudos. Contenido no confiable.",
            "parameters": {
                "queue_name": {"description": "Nombre de la cola de entrada (variable queue_name)."}
            },
            "messages": {
                "webhookMeta": {"$ref": "#/components/messages/WebhookMeta"},
                "sobreCustomWhatsApp": {"$ref": "#/components/messages/SobreCustomWhatsApp"},
            },
            "bindings": {
                "amqp": {
                    "is": "queue",
                    "queue": {"durable": True, "exclusive": False, "autoDelete": False},
                    "bindingVersion": AMQP,
                }
            },
        },
        "salida": {
            "address": "meta-classified",
            "description": (
                "Cola durable con los resultados. El nombre es el valor por defecto de "
                "output_queue_name; la clave de enrutado por defecto es meta.classified."
            ),
            "messages": {
                "resultadoClasificado": {"$ref": "#/components/messages/ResultadoClasificado"}
            },
            "bindings": {
                "amqp": {
                    "is": "queue",
                    "queue": {"name": "meta-classified", "durable": True, "exclusive": False, "autoDelete": False},
                    "bindingVersion": AMQP,
                }
            },
        },
    },
    "operations": {
        "recibirWebhook": {
            "action": "receive",
            "channel": {"$ref": "#/channels/entrada"},
            "summary": "Consume un webhook, con confirmación manual y prefetch 1.",
            "description": (
                "ACK cuando el pipeline termina, también si el payload se descarta por origen no "
                "soportado o por ser inválido. NACK sin reencolar ante una excepción."
            ),
            "messages": [
                {"$ref": "#/channels/entrada/messages/webhookMeta"},
                {"$ref": "#/channels/entrada/messages/sobreCustomWhatsApp"},
            ],
            "bindings": {"amqp": {"ack": True, "bindingVersion": AMQP}},
        },
        "publicarResultado": {
            "action": "send",
            "channel": {"$ref": "#/channels/salida"},
            "summary": "Publica el resultado de clasificar un mensaje.",
            "description": (
                "Un resultado por mensaje procesado, también cuando los guardrails lo bloquean "
                "(permitido = false). Hoy sin confirmación del broker ni mensajes persistentes (amenaza T6)."
            ),
            "messages": [{"$ref": "#/channels/salida/messages/resultadoClasificado"}],
        },
    },
    "components": {
        "securitySchemes": {
            "usuarioBroker": {
                "type": "userPassword",
                "description": "Usuario y contraseña del broker (qms_user, qms_password).",
            }
        },
        "messages": {
            "WebhookMeta": {
                "name": "WebhookMeta",
                "title": "Webhook de Messenger, WhatsApp o Instagram",
                "contentType": "application/json",
                "payload": {"$ref": "#/components/schemas/WebhookMeta"},
            },
            "SobreCustomWhatsApp": {
                "name": "SobreCustomWhatsApp",
                "title": "Sobre custom de WhatsApp (jwe_body)",
                "contentType": "application/json",
                "payload": {"$ref": "#/components/schemas/SobreCustomWhatsApp"},
            },
            "ResultadoClasificado": {
                "name": "ResultadoClasificado",
                "title": "Resultado de la clasificación",
                "contentType": "application/json",
                "payload": {"$ref": "#/components/schemas/ResultadoClasificado"},
            },
        },
        "schemas": dict(sorted(schemas.items())),
    },
}

HEADER = (
    "# Contrato AsyncAPI de ms-python-metamsghandler (fase 02-design, Gate 1).\n"
    "# Estado: review. Fecha: 2026-10-12. Versión: 0.2.0.\n"
    "# Los esquemas ResultadoClasificado, Intencion, Adjunto, Origen y TipoRespuesta se\n"
    "# generan con model_json_schema() desde src/domain/models: regenerar, no editar a mano.\n"
    "# WebhookMeta y SobreCustomWhatsApp describen solo lo que leen los parsers.\n"
)

out = sys.argv[1]
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(HEADER)
    yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True, width=100)
print("escrito", out, "schemas:", ", ".join(doc["components"]["schemas"]))
