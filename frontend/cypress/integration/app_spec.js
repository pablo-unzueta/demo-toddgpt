describe('ToddGPT App', () => {
  beforeEach(() => {
    cy.visit('http://localhost:3000')
  })

  it('loads the app', () => {
    cy.contains('ToddGPT').should('be.visible')
  })

  it('can send a message and receive a response', () => {
    cy.intercept('POST', 'http://127.0.0.1:8000/query', {
      statusCode: 200,
      body: { response: 'Test response', html: '<p>Test HTML</p>' }
    }).as('sendMessage')

    cy.get('.chat-input').type('Test message')
    cy.get('.send-button').click()

    cy.wait('@sendMessage')

    cy.contains('Test message').should('be.visible')
    cy.contains('Test response').should('be.visible')
    cy.contains('Test HTML').should('be.visible')
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
})