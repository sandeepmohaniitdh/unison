import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderApp } from '../test/fakeApi'
import ErrorBoundary from './ErrorBoundary'
import { Alert, Confirm, Empty, ErrorMessage, Loading, Modal, PageError } from './Feedback'
import { Select, TextField, Toggle } from './FormControls'
import Pagination from './Pagination'

describe('feedback', () => {
  it('shows alerts, errors and empty states', () => {
    render(
      <>
        <Alert tone="success">Saved</Alert>
        <Alert>{null}</Alert>
        <ErrorMessage error={{ status: 500, message: 'Server broke', requestId: 'abc' }} />
        <ErrorMessage error={null} />
        <Empty>Nothing here</Empty>
        <Loading />
        <PageError error={{ status: 404 }} />
      </>,
    )
    expect(screen.getByText('Loading…')).toBeTruthy()
    expect(screen.getByText('Saved')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('(request abc)')
    expect(screen.getByText('Nothing here')).toBeTruthy()
    expect(screen.getByText('Not found')).toBeTruthy()
  })

  it('closes a dialog with Escape and confirms with the button', () => {
    const onClose = vi.fn()
    const onConfirm = vi.fn()
    const { unmount } = render(
      <Modal title="Hello" onClose={onClose}>
        <input aria-label="Inside" />
      </Modal>,
    )
    expect(document.activeElement).toBe(screen.getByLabelText('Inside'))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
    unmount()
    render(
      <Confirm title="Delete?" danger confirmLabel="Delete" onConfirm={onConfirm} onCancel={onClose}>
        Sure?
      </Confirm>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onConfirm).toHaveBeenCalled()
  })
})

describe('pagination', () => {
  it('shows at most five numbers and moves between pages', () => {
    const onChange = vi.fn()
    render(<Pagination page={5} size={10} total={100} onChange={onChange} />)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Previous', '3', '4', '5', '6', '7', 'Next'])
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(onChange).toHaveBeenCalledWith(6)
  })

  it('hides itself for a single page', () => {
    const { container } = render(<Pagination page={1} size={10} total={4} onChange={() => {}} />)
    expect(container.innerHTML).toBe('')
  })
})

describe('form controls', () => {
  it('labels fields and reports changes', () => {
    const onSelect = vi.fn()
    const onToggle = vi.fn()
    render(
      <>
        <TextField label="Title" defaultValue="x" />
        <Select label="Role" options={[{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }]} value="a" onChange={onSelect} />
        <Toggle checked={false} label="Email me" onChange={onToggle} />
      </>,
    )
    expect(screen.getByLabelText('Title').value).toBe('x')
    fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'b' } })
    expect(onSelect).toHaveBeenCalledWith('b')
    fireEvent.click(screen.getByRole('switch', { name: 'Email me' }))
    expect(onToggle).toHaveBeenCalledWith(true)
  })
})

describe('error boundary', () => {
  it('shows a message instead of a blank page', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    function Broken() {
      throw new Error('boom')
    }
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Something went wrong on this page')).toBeTruthy()
    spy.mockRestore()
  })
})

describe('component gallery', () => {
  it('renders every shared component on /dev/components', async () => {
    renderApp('/dev/components')
    expect((await screen.findAllByRole('button')).length).toBeGreaterThan(5)
  })
})
