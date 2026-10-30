import { useParams } from 'react-router-dom'
import EmployeeProfileDetails from '../components/EmployeeProfileDetails.jsx'

/**
 * Route wrapper for the employee profile detail view.
 *
 * @returns {JSX.Element}
 */
export default function EmployeeProfile() {
  const { employeeId } = useParams()
  return <EmployeeProfileDetails employeeId={employeeId} />
}
