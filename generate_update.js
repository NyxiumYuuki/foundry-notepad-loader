const Y = require('yjs')
const { v4: uuidv4 } = require('uuid')

const chunks = []
process.stdin.on('data', chunk => chunks.push(chunk))
process.stdin.on('end', () => {
    const content = Buffer.concat(chunks).toString('utf8')
    const doc = new Y.Doc()
    const fragment = doc.getXmlFragment('content')

    doc.transact(() => {
        const textNode = new Y.XmlText()
        textNode.setAttribute('type', 'paragraph')
        textNode.setAttribute('id', uuidv4())
        textNode.insert(0, content)
        fragment.insert(0, [textNode])
    })

    const update = Y.encodeStateAsUpdate(doc)
    process.stdout.write(Buffer.from(update).toString('base64'))
})
