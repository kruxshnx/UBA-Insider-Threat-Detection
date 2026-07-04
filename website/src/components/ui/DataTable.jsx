import { cn } from '../../lib/utils'

/**
 * DataTable — a styled, responsive table. Always renders inside a horizontal
 * scroll wrapper so wide tables scroll within their own container (the page
 * body never scrolls horizontally).
 *
 * @param {Array<{key:string,header:string,align?:'left'|'right'|'center',numeric?:boolean,width?:string,render?:(row,i)=>node,className?:string}>} columns
 * @param {Array<object>} rows
 * @param {(row,i)=>string|number} [rowKey]   Key extractor (defaults to index).
 * @param {(row,i)=>void} [onRowClick]        Makes rows clickable + keyboard-focusable.
 * @param {React.ReactNode} [empty]           Rendered when rows is empty (e.g. <EmptyState/>).
 * @param {string} [className]                Extra classes on the scroll wrapper.
 *
 * @example
 * <DataTable
 *   columns={[
 *     { key:'user', header:'User' },
 *     { key:'score', header:'Risk', numeric:true, render:(r)=><RiskBadge level={r.band} score={r.score}/> },
 *   ]}
 *   rows={users}
 *   rowKey={(r)=>r.id}
 *   onRowClick={(r)=>navigate(`/forensics?u=${r.id}`)}
 *   empty={<EmptyState title="No users" />}
 * />
 */
export function DataTable({ columns = [], rows = [], rowKey, onRowClick, empty, className = '' }) {
  const alignClass = (col) =>
    col.numeric || col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'

  if (rows.length === 0 && empty) {
    return <div>{empty}</div>
  }

  return (
    <div className={cn('table-scroll', className)}>
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={alignClass(col)} style={col.width ? { width: col.width } : undefined}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const clickable = typeof onRowClick === 'function'
            return (
              <tr
                key={rowKey ? rowKey(row, i) : i}
                onClick={clickable ? () => onRowClick(row, i) : undefined}
                onKeyDown={clickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(row, i) } } : undefined}
                tabIndex={clickable ? 0 : undefined}
                role={clickable ? 'button' : undefined}
                className={clickable ? 'cursor-pointer' : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(alignClass(col), (col.numeric || col.align === 'right') && 'num', col.className)}
                  >
                    {col.render ? col.render(row, i) : row[col.key]}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default DataTable
