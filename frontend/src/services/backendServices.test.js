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
})
