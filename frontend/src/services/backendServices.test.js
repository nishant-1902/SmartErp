import { afterEach, describe, expect, it } from 'vitest'
import apiClient from './apiClient.js'
import {
  createEmployee,
  deactivateEmployee,
  listEmployees,
} from './employeeService.js'
import {
  createDepartment,
  listDepartmentEmployees,
  listDepartments,
} from './departmentService.js'
import {
  activateUser,
  createUser,
  deactivateUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from './userService.js'
import { listAuditLogs } from './auditService.js'
import {
  changePassword,
  confirmPasswordReset,
  requestPasswordReset,
} from './authService.js'

const originalAdapter = apiClient.defaults.adapter

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
})

describe('backend API services', () => {
  it('uses the employee list endpoint and unwraps data and pagination metadata', async () => {
    let request
    apiClient.defaults.adapter = async (config) => {
      request = config
      return {
        status: 200,
        headers: {},
        config,
        data: {
          success: true,
          data: { employees: [{ id: 'employee-1' }] },
          meta: { page: 2, page_size: 10, total: 14, total_pages: 2 },
        },
      }
    }

    const result = await listEmployees(
      { page: 2, page_size: 10, status: 'active' },
      { signal: new AbortController().signal },
    )

    expect(request.url).toBe('/employees/')
    expect(request.params).toEqual({ page: 2, page_size: 10, status: 'active' })
    expect(result.items).toEqual([{ id: 'employee-1' }])
    expect(result.meta.total_pages).toBe(2)
  })

  it('posts create requests and sends deactivate as a DELETE without removing the record', async () => {
    const requests = []
    apiClient.defaults.adapter = async (config) => {
      requests.push(config)
      return {
        status: 200,
        headers: {},
        config,
        data: { success: true, data: { employee: { id: 'employee-1' } } },
      }
    }

    await createEmployee({ employee_code: 'EMP-01' })
    await deactivateEmployee('employee-1')

    expect(requests.map(({ method, url }) => [method, url])).toEqual([
      ['post', '/employees/'],
      ['delete', '/employees/employee-1/'],
    ])
  })

  it('uses department list and department employee endpoints', async () => {
    const requests = []
    apiClient.defaults.adapter = async (config) => {
      requests.push(config)
      return {
        status: 200,
        headers: {},
        config,
        data: {
          success: true,
          data: {
            departments: [{ id: 'department-1' }],
            employees: [{ id: 'employee-1' }],
          },
          meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
        },
      }
    }

    const departments = await listDepartments({ page: 1 })
    const employees = await listDepartmentEmployees('department-1', {
      page: 1,
      page_size: 10,
    })

    expect(requests.map(({ url }) => url)).toEqual([
      '/departments/',
      '/departments/department-1/employees/',
    ])
    expect(departments.items).toEqual([{ id: 'department-1' }])
    expect(employees.items).toEqual([{ id: 'employee-1' }])
  })

  it('posts department create requests with the supplied validated body', async () => {
    let request
    apiClient.defaults.adapter = async (config) => {
      request = config
      return {
        status: 201,
        headers: {},
        config,
        data: { success: true, data: { department: { id: 'department-1' } } },
      }
    }

    const values = { code: 'OPS', name: 'Operations', manager_employee_id: null }
    const result = await createDepartment(values)

    expect(request.method).toBe('post')
    expect(request.url).toBe('/departments/')
    expect(request.data).toBe(JSON.stringify(values))
    expect(result.id).toBe('department-1')
  })

  it('uses the user-management API paths and unwraps list metadata', async () => {
    const requests = []
    apiClient.defaults.adapter = async (config) => {
      requests.push(config)
      return {
        status: 200,
        headers: {},
        config,
        data: {
          success: true,
          data: { users: [{ id: 'user-1' }], user: { id: 'user-1' }, message: 'Reset' },
          meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
        },
      }
    }

    const result = await listUsers(
      { page: 1, page_size: 20, role: 'employee', is_active: false },
      { signal: new AbortController().signal },
    )
    await createUser({ email: 'new@example.com' })
    await updateUser('user-1', { full_name: 'New Name' })
    await activateUser('user-1')
    await deactivateUser('user-1')
    await resetUserPassword('user-1')

    expect(result.items).toEqual([{ id: 'user-1' }])
    expect(result.meta.total).toBe(1)
    expect(requests.map(({ method, url }) => [method, url])).toEqual([
      ['get', '/users/'],
      ['post', '/users/'],
      ['patch', '/users/user-1/'],
      ['post', '/users/user-1/activate/'],
      ['post', '/users/user-1/deactivate/'],
      ['post', '/users/user-1/reset-password/'],
    ])
    expect(requests[0].params).toEqual({
      page: 1,
      page_size: 20,
      role: 'employee',
      is_active: false,
    })
  })

  it('converts audit date filters to inclusive UTC day boundaries', async () => {
    let request
    apiClient.defaults.adapter = async (config) => {
      request = config
      return {
        status: 200,
        headers: {},
        config,
        data: {
          success: true,
          data: { audit_logs: [{ id: 'event-1' }] },
          meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
        },
      }
    }

    const result = await listAuditLogs({
      page: 1,
      user: '0123456789abcdef01234567',
      start_date: '2026-10-01',
      end_date: '2026-10-30',
    })

    expect(request.url).toBe('/audit-logs/')
    expect(request.params).toEqual({
      page: 1,
      user: '0123456789abcdef01234567',
      start_date: '2026-10-01T00:00:00.000Z',
      end_date: '2026-10-30T23:59:59.999Z',
    })
    expect(result.items).toEqual([{ id: 'event-1' }])
  })

  it('uses the account password and reset endpoints with their expected payloads', async () => {
    const requests = []
    apiClient.defaults.adapter = async (config) => {
      requests.push(config)
      return {
        status: 200,
        headers: {},
        config,
        data: { success: true, data: { message: 'Request accepted.' } },
      }
    }

    await changePassword({
      old_password: 'old-password',
      new_password: 'new-password',
      confirm_password: 'new-password',
    })
    await requestPasswordReset('alex@example.com')
    await confirmPasswordReset({
      email: 'alex@example.com',
      token: 'one-time-token',
      password: 'new-password',
      confirm_password: 'new-password',
    })

    expect(requests.map(({ method, url }) => [method, url])).toEqual([
      ['post', '/auth/change-password/'],
      ['post', '/auth/password-reset/request/'],
      ['post', '/auth/password-reset/confirm/'],
    ])
    expect(JSON.parse(requests[1].data)).toEqual({ email: 'alex@example.com' })
    expect(JSON.parse(requests[2].data)).toMatchObject({
      token: 'one-time-token',
      email: 'alex@example.com',
    })
  })
})
