import ArtifactLink from './ArtifactLink.js'
import ArtifactItems from './ArtifactItems.js'
import SkillAction from './SkillAction.js'

export default function ArtifactCard({ card, actionBusy = false, actionsDisabled = false, onAction }) {
  return (
    <article className={`artifact-card artifact-${card.kind}`} aria-labelledby={`${card.id}-title`}>
      <header className="artifact-header">
        <div>
          <span className="artifact-kind">{card.kind.replaceAll('-', ' ')}</span>
          <h3 id={`${card.id}-title`}>{card.title}</h3>
        </div>
        {card.badge && <span className="artifact-badge">{card.badge}</span>}
      </header>
      {card.body && <p className="artifact-body">{card.body}</p>}
      {card.items && <ArtifactItems items={card.items} />}
      {card.link && <ArtifactLink link={card.link} />}
      {card.action && (
        <SkillAction
          action={card.action}
          busy={actionBusy}
          disabled={actionsDisabled}
          onAction={onAction}
        />
      )}
    </article>
  )
}
