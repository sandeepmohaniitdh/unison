import Card from './Card'
import Icon from './Icon'

// "AI suggests 9" chip shown next to a rubric score.
export function AiSuggestion({ children }) {
  return (
    <span className="sug">
      <Icon name="sparkle" size={12} />
      {children}
    </span>
  )
}

// The AI feedback draft panel on the review page.
//   <AiFeedbackPanel warning="Only the first 12,000 characters..." footnote="..." actions={...}>
//     <p className="small"><b>Implementation, 20/25:</b> ...</p>
//   </AiFeedbackPanel>
export function AiFeedbackPanel({ title = 'AI feedback draft', warning, footnote, actions, width = 300, children }) {
  return (
    <Card as="section" className="ai col gap12" style={{ width }} aria-label={title}>
      <div className="row gap8 text-primary">
        <Icon name="sparkle" size={20} />
        <h3>{title}</h3>
      </div>
      {warning && (
        <div className="row gap8 ai-warning">
          <Icon name="clock" size={16} />
          <span className="small">{warning}</span>
        </div>
      )}
      {children}
      {footnote && <p className="tiny muted">{footnote}</p>}
      {actions && <div className="row gap8">{actions}</div>}
    </Card>
  )
}
