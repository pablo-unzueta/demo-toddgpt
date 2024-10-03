describe('ToddGPT App', () => {
  beforeEach(() => {
    cy.visit('http://localhost:3000')
  })

  it('loads the app', () => {
    cy.contains('ToddGPT').should('be.visible')
  })

  it('can send a message and receive a text response', () => {
    cy.intercept('POST', 'http://127.0.0.1:8000/query', {
      statusCode: 200,
      body: { response: 'Test response' }
    }).as('sendMessage')

    cy.get('.chat-input').type('Test message')
    cy.get('.send-button').click()

    cy.wait('@sendMessage')

    cy.contains('Test message').should('be.visible')
    cy.contains('Test response').should('be.visible')
  })

  it('can receive and render HTML response', () => {
    cy.intercept('POST', 'http://127.0.0.1:8000/query', {
      statusCode: 200,
      body: { 
        response: 'Here is some HTML:',
        html: '<div class="test-html"><h1>Test HTML Heading</h1><p>This is a paragraph.</p></div>'
      }
    }).as('sendHTMLMessage')

    cy.get('.chat-input').type('Show me some HTML')
    cy.get('.send-button').click()

    cy.wait('@sendHTMLMessage')

    cy.contains('Show me some HTML').should('be.visible')
    cy.contains('Here is some HTML:').should('be.visible')
    
    // Check if HTML is rendered correctly
    cy.get('.message-html').within(() => {
      cy.get('.test-html').should('exist')
      cy.get('h1').should('have.text', 'Test HTML Heading')
      cy.get('p').should('have.text', 'This is a paragraph.')
    })
  })

  it('handles errors', () => {
    cy.intercept('POST', 'http://127.0.0.1:8000/query', {
      statusCode: 500,
      body: 'Server error'
    }).as('sendMessage')

    cy.get('.chat-input').type('Test message')
    cy.get('.send-button').click()

    cy.wait('@sendMessage')

    cy.contains('Test message').should('be.visible')
    cy.contains('An error occurred.').should('be.visible')
  })

  it('can display an image as HTML using base64 encoding', () => {
    // This is a small, sample base64 encoded image (1x1 pixel)
    const base64Image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==';
    const imageHtml = `<img src="${base64Image}" alt="HHTDA Spectrum" style="width:300px;height:200px;" />`;

    cy.intercept('POST', 'http://127.0.0.1:8000/query', {
      statusCode: 200,
      body: { 
        response: 'Here is the HHTDA spectrum:',
        html: imageHtml
      }
    }).as('sendImageMessage')

    cy.get('.chat-input').type('Show me the HHTDA spectrum')
    cy.get('.send-button').click()

    cy.wait('@sendImageMessage')

    cy.contains('Show me the HHTDA spectrum').should('be.visible')
    cy.contains('Here is the HHTDA spectrum:').should('be.visible')
    
    // Check if the image is rendered correctly
    cy.get('.message-html img')
      .should('be.visible')
      .and('have.attr', 'src')
      .and('include', 'data:image/png;base64,')
    
    cy.get('.message-html img')
      .should('have.attr', 'alt', 'HHTDA Spectrum')
      .and('have.attr', 'style', 'width:300px;height:200px;')
  })
})