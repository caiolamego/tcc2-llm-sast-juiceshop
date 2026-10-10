declare const libxml2: any

function vulnerable(data: string) {
  // ruleid: tcc.xml.security.external-entity-expansion
  const option = libxml2.ParseOption.XML_PARSE_NOENT | libxml2.ParseOption.XML_PARSE_DTDLOAD | libxml2.ParseOption.XML_PARSE_NOBLANKS
  return libxml2.XmlDocument.fromString(data, { option })
}

function safeNoExternalEntities(data: string) {
  // ok: tcc.xml.security.external-entity-expansion
  const option = libxml2.ParseOption.XML_PARSE_NONET | libxml2.ParseOption.XML_PARSE_NOBLANKS
  return libxml2.XmlDocument.fromString(data, { option })
}
