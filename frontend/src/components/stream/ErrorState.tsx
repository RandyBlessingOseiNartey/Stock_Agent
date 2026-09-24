interface ErrorStateProps {
  message: string
  title?: string
  onRetry?: () => void
}

/** The app's one error presentation, shared by all three modes. */
export function ErrorState({ message, title = 'Something went wrong', onRetry }: ErrorStateProps) {
  return (
    <div className="error-state" role="alert">
      <span className="error-state__icon" aria-hidden="true">!</span>
      <div className="error-state__body">
        <p className="error-state__title">{title}</p>
        <p className="error-state__message">{message}</p>
        {onRetry && (
          <button type="button" className="btn-secondary" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
